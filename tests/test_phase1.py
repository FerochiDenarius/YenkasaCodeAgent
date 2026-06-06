from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.agents.database_agent import DatabaseAgent
from app.agents.repository_agent import RepositoryAgent
from app.config.settings import Settings
from app.core.orchestrator import YenkasaCodeOrchestrator
from app.main import app
from app.models.agent import AgentQueryRequest
from app.repositories.memory_embeddings_repository import MemoryEmbeddingsRepository
from app.repositories.repo_chunks_repository import RepoChunksRepository
from app.repositories.repository_intelligence_repository import RepositoryIntelligenceRepository
from app.services.mongodb_service import MongoDBService


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    payload = response.json()
    assert payload == {
        "status": "ok",
        "version": "0.1.0",
        "registered_agents": 3,
    }


def test_agent_query_routes_to_system_agent() -> None:
    with TestClient(app) as client:
        response = client.post("/api/agent/query", json={"query": "status"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    payload = response.json()
    assert payload == {
        "agent": "system",
        "success": True,
        "result": {
            "message": "YenkasaCode Agent foundation is online.",
            "query": "status",
            "context": {},
            "phase": "phase_1_foundation",
        },
        "error": None,
    }


def test_agent_discovery() -> None:
    with TestClient(app) as client:
        response = client.get("/api/agent/agents")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["name"] == "system"
    assert payload[1]["name"] == "DatabaseAgent"
    assert payload[2]["name"] == "RepositoryAgent"


def test_request_id_header_is_preserved() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"


def test_agent_metrics() -> None:
    with TestClient(app) as client:
        response = client.get("/api/agent/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "total_requests",
        "successful_requests",
        "failed_requests",
        "registered_agents",
        "database_queries_total",
        "database_query_failures",
        "database_query_duration_ms",
        "repository_queries_total",
        "repository_query_failures",
        "repository_query_duration_ms",
    }
    assert payload["registered_agents"] == ["system", "DatabaseAgent", "RepositoryAgent"]


class FakeCommandDatabase:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str | None]] = []

    async def command(self, command: str, collection_name: str | None = None) -> dict[str, int] | dict[str, str]:
        self.commands.append((command, collection_name))
        if command == "ping":
            return {"ok": 1}
        return {"storageSize": 2048, "size": 1024, "count": 12}


class FakeCountCollection:
    async def count_documents(self, filter_query: dict[str, object]) -> int:
        assert filter_query == {}
        return 42


class FakeLatestCursor:
    def sort(self, field: str, direction: int) -> "FakeLatestCursor":
        assert field == "indexed_at"
        assert direction == -1
        return self

    def limit(self, count: int) -> "FakeLatestCursor":
        assert count == 1
        return self

    async def to_list(self, length: int | None) -> list[dict[str, str]]:
        assert length == 1
        return [{"repo_name": "yenkasaChat", "file_path": "app/main.py", "indexed_at": "2026-06-06T12:00:00Z"}]


class FakeLatestCollection:
    def find(self, filter_query: dict[str, object], projection: dict[str, int]) -> FakeLatestCursor:
        assert filter_query == {}
        assert projection["_id"] == 0
        return FakeLatestCursor()


class FakeAggregateCursor:
    async def to_list(self, length: int | None) -> list[dict[str, int | str]]:
        assert length is None
        return [{"repository": "yenkasaChat", "chunk_count": 9}]


class FakeAggregateCollection:
    def aggregate(self, pipeline: list[dict[str, object]]) -> FakeAggregateCursor:
        assert pipeline[-1] == {"$project": {"_id": 0, "repository": "$_id", "chunk_count": 1}}
        return FakeAggregateCursor()


class FakeMongoDBService:
    def __init__(self, collection: object | None = None) -> None:
        self.command_database = FakeCommandDatabase()
        self.fake_collection = collection or FakeCountCollection()

    def database(self) -> FakeCommandDatabase:
        return self.command_database

    def collection(self, name: str) -> object:
        assert name in {"repo_chunks", "memory_embeddings"}
        return self.fake_collection

    async def count_documents(self, collection_name: str, filter_query: dict[str, object] | None = None) -> int:
        return await self.collection(collection_name).count_documents(filter_query or {})

    async def collection_stats(self, collection_name: str) -> dict[str, object]:
        return await self.database().command("collStats", collection_name)

    async def latest_record(
        self,
        collection_name: str,
        *,
        sort_field: str,
        projection: dict[str, object] | None = None,
    ) -> dict[str, object] | None:
        cursor = self.collection(collection_name).find({}, projection or {}).sort(sort_field, -1).limit(1)
        records = await cursor.to_list(length=1)
        return records[0] if records else None

    async def aggregate(self, collection_name: str, pipeline: list[dict[str, object]]) -> list[dict[str, object]]:
        return await self.collection(collection_name).aggregate(pipeline).to_list(length=None)


def test_mongodb_service_successful_connection() -> None:
    service = MongoDBService(Settings(mongodb_uri="mongodb://example", mongodb_database="test"))
    fake_database = FakeCommandDatabase()
    service.database = lambda: fake_database

    assert asyncio.run(service.ping()) is True
    assert fake_database.commands == [("ping", None)]


def test_database_repository_collection_counts() -> None:
    repository = RepoChunksRepository(FakeMongoDBService())

    assert asyncio.run(repository.count()) == 42


def test_database_repository_stats_retrieval() -> None:
    repository = MemoryEmbeddingsRepository(FakeMongoDBService())

    stats = asyncio.run(repository.stats())

    assert stats["storageSize"] == 2048
    assert stats["count"] == 12


def test_database_repository_latest_file_retrieval() -> None:
    repository = RepoChunksRepository(FakeMongoDBService(collection=FakeLatestCollection()))

    latest_file = asyncio.run(repository.latest_indexed_file())

    assert latest_file == {
        "repo_name": "yenkasaChat",
        "file_path": "app/main.py",
        "indexed_at": "2026-06-06T12:00:00Z",
    }


def test_database_repository_aggregation_query() -> None:
    repository = RepoChunksRepository(FakeMongoDBService(collection=FakeAggregateCollection()))

    result = asyncio.run(repository.top_repositories_by_chunk_count(limit=1))

    assert result == [{"repository": "yenkasaChat", "chunk_count": 9}]


def test_database_agent_routes_supported_question_to_repository() -> None:
    mongodb = FakeMongoDBService(collection=FakeAggregateCollection())
    agent = DatabaseAgent(
        repo_chunks_repository=RepoChunksRepository(mongodb),
        memory_embeddings_repository=MemoryEmbeddingsRepository(mongodb),
    )

    response = asyncio.run(agent.execute("What are the top repositories by chunk count?", {"limit": 1}))

    assert response.agent == "DatabaseAgent"
    assert response.success is True
    assert response.result == {"top_repositories": [{"repository": "yenkasaChat", "chunk_count": 9}]}


class FakeRepositoryMongoDBService:
    async def aggregate(self, collection_name: str, pipeline: list[dict[str, object]]) -> list[dict[str, object]]:
        assert collection_name == "repo_chunks"
        pipeline_text = str(pipeline)
        if "latest_indexed_at" in pipeline_text:
            return [
                {
                    "repository": "yenkasaChat",
                    "chunk_count": 20,
                    "file_count": 4,
                    "latest_indexed_at": "2026-06-06T12:00:00Z",
                }
            ]
        if "language" in pipeline_text and "$match" in pipeline_text:
            return [{"language": "kotlin", "chunk_count": 8, "file_count": 2}]
        if "language" in pipeline_text:
            return [
                {"language": "kotlin", "chunk_count": 8, "file_count": 2},
                {"language": "python", "chunk_count": 5, "file_count": 1},
            ]
        if "indexed_at" in pipeline_text and "$limit" in pipeline_text:
            return [
                {
                    "repository": "yenkasaChat",
                    "file_path": "android/MainActivity.kt",
                    "indexed_at": "2026-06-06T12:00:00Z",
                }
            ]
        if "chunk_count" in pipeline_text:
            return [{"repository": "yenkasaChat", "chunk_count": 20}]
        return [{"missing_metadata_count": 0}]


def build_repository_agent(mongodb: FakeRepositoryMongoDBService | None = None) -> RepositoryAgent:
    mongodb = mongodb or FakeRepositoryMongoDBService()
    return RepositoryAgent(
        repo_chunks_repository=RepoChunksRepository(mongodb),
        repository_intelligence_repository=RepositoryIntelligenceRepository(mongodb),
    )


def test_repository_inventory() -> None:
    response = asyncio.run(build_repository_agent().execute("Which repositories are indexed?"))

    assert response.agent == "RepositoryAgent"
    assert response.success is True
    assert response.result == {
        "repositories": [
            {
                "repository": "yenkasaChat",
                "chunk_count": 20,
                "file_count": 4,
                "latest_indexed_at": "2026-06-06T12:00:00Z",
            }
        ]
    }


def test_repository_statistics() -> None:
    response = asyncio.run(build_repository_agent().execute("Which repository has the most chunks?"))

    assert response.success is True
    assert response.result == {"top_repositories": [{"repository": "yenkasaChat", "chunk_count": 20}]}


def test_repository_language_breakdown() -> None:
    response = asyncio.run(build_repository_agent().execute("Language breakdown"))

    assert response.success is True
    assert response.result == {
        "language_breakdown": [
            {"language": "kotlin", "chunk_count": 8, "file_count": 2},
            {"language": "python", "chunk_count": 5, "file_count": 1},
        ]
    }


def test_repository_language_file_count() -> None:
    response = asyncio.run(build_repository_agent().execute("How many Kotlin files exist?"))

    assert response.success is True
    assert response.result == {"language": {"language": "kotlin", "chunk_count": 8, "file_count": 2}}


def test_repository_latest_activity() -> None:
    response = asyncio.run(build_repository_agent().execute("Latest repository activity"))

    assert response.success is True
    assert response.result == {
        "latest_repository_activity": {
            "repository": "yenkasaChat",
            "file_path": "android/MainActivity.kt",
            "indexed_at": "2026-06-06T12:00:00Z",
        }
    }


def test_repository_agent_routing_behavior() -> None:
    orchestrator = YenkasaCodeOrchestrator(mongodb=FakeRepositoryMongoDBService())
    response = asyncio.run(orchestrator.route(AgentQueryRequest(query="Show repository inventory")))

    assert response.agent == "RepositoryAgent"
    assert response.success is True
