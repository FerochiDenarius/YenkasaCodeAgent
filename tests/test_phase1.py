from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.agents.cloudrun_agent import CloudRunAgent
from app.agents.code_audit_agent import CodeAuditAgent
from app.agents.database_agent import DatabaseAgent
from app.agents.observability_agent import ObservabilityAgent
from app.agents.product_builder_agent import ProductBuilderAgent
from app.agents.refactor_agent import RefactorAgent
from app.agents.registry import AgentRegistry
from app.agents.repository_agent import RepositoryAgent
from app.agents.vector_search_agent import VectorSearchAgent
from app.config.settings import Settings
from app.core.orchestrator import YenkasaCodeOrchestrator
from app.main import app
from app.models.agent import AgentQueryRequest
from app.models.agent import AgentResponse
from app.orchestrator import ExecutionPlanner
from app.orchestrator import IntentClassifier
from app.orchestrator import ResponseSynthesizer
from app.orchestrator import YenkasaIntelligenceOrchestrator
from app.orchestrator.reasoning_engine import ReasoningEngine
from app.repositories.memory_embeddings_repository import MemoryEmbeddingsRepository
from app.repositories.repo_chunks_repository import RepoChunksRepository
from app.repositories.repository_intelligence_repository import RepositoryIntelligenceRepository
from app.repositories.vector_search_repository import VectorSearchRepository
from app.services.audit_service import AuditService
from app.services.cloudrun_service import CloudRunService
from app.services.mongodb_service import MongoDBService
from app.services.observability_service import ObservabilityService
from app.services.product_builder_service import ProductBuilderService
from app.services.refactor_service import RefactorService
from app.security.auth import required_role_for_query
from app.security.auth import _configured_keys
import app.security.auth as auth_module


VIEWER_HEADERS = {"X-API-Key": "dev-viewer-key"}
DEVELOPER_HEADERS = {"X-API-Key": "dev-developer-key"}
ADMIN_HEADERS = {"X-API-Key": "dev-admin-key"}


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers=VIEWER_HEADERS)

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    payload = response.json()
    assert payload == {
        "status": "ok",
        "version": "0.1.0",
        "registered_agents": 9,
    }


def test_agent_query_routes_to_system_agent() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/agent/query",
            json={"query": "status", "agent": "system"},
            headers=VIEWER_HEADERS,
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    payload = response.json()
    assert payload["agent"] == "system"
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["result"]["answer"] == "I collected evidence for: message, query, context, phase."
    assert payload["result"]["facts"]["message"] == "YenkasaCode Agent foundation is online."
    assert payload["evidence_package"]["agent"] == "system"
    assert payload["reasoning"]["finalized"] is True


def test_agent_discovery() -> None:
    with TestClient(app) as client:
        response = client.get("/api/agent/agents", headers=VIEWER_HEADERS)

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["name"] == "system"
    assert payload[1]["name"] == "DatabaseAgent"
    assert payload[2]["name"] == "RepositoryAgent"
    assert payload[3]["name"] == "VectorSearchAgent"
    assert payload[4]["name"] == "CodeAuditAgent"
    assert payload[5]["name"] == "RefactorAgent"
    assert payload[6]["name"] == "CloudRunAgent"
    assert payload[7]["name"] == "ObservabilityAgent"
    assert payload[8]["name"] == "ProductBuilderAgent"


def test_request_id_header_is_preserved() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-request-id", **VIEWER_HEADERS})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"


def test_agent_metrics() -> None:
    with TestClient(app) as client:
        response = client.get("/api/agent/metrics", headers=ADMIN_HEADERS)

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
        "vector_queries_total",
        "vector_query_failures",
        "vector_query_duration_ms",
        "audit_queries_total",
        "audit_query_failures",
        "audit_query_duration_ms",
        "refactor_queries_total",
        "refactor_query_failures",
        "refactor_query_duration_ms",
        "cloudrun_queries_total",
        "cloudrun_query_failures",
        "cloudrun_query_duration_ms",
        "observability_queries_total",
        "observability_query_failures",
        "observability_query_duration_ms",
        "yio_requests_total",
        "yio_failures_total",
        "yio_execution_duration_ms",
        "product_builder_queries_total",
        "product_builder_query_failures",
        "product_builder_query_duration_ms",
    }
    assert payload["registered_agents"] == [
        "system",
        "DatabaseAgent",
        "RepositoryAgent",
        "VectorSearchAgent",
        "CodeAuditAgent",
        "RefactorAgent",
        "CloudRunAgent",
        "ObservabilityAgent",
        "ProductBuilderAgent",
    ]


def test_protected_endpoint_rejects_missing_api_key() -> None:
    with TestClient(app) as client:
        response = client.get("/api/agent/agents")

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing API key."}


def test_viewer_cannot_access_admin_metrics() -> None:
    with TestClient(app) as client:
        response = client.get("/api/agent/metrics", headers=VIEWER_HEADERS)

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient role."}


def test_yenkasa_ai_bearer_token_can_authorize_agent_requests(monkeypatch) -> None:
    async def fake_authenticate_yenkasa_ai_token(request, token):
        assert token == "test-yenkasa-ai-token"
        return auth_module.AuthenticatedPrincipal(
            role="admin",
            key_hash="test-yenkasa-ai-principal",
            subject="test-user",
            email="test@example.com",
            source="yenkasa_ai",
        )

    monkeypatch.setattr(auth_module, "_authenticate_yenkasa_ai_token", fake_authenticate_yenkasa_ai_token)

    with TestClient(app) as client:
        response = client.get(
            "/api/agent/metrics",
            headers={"X-Yenkasa-AI-Authorization": "Bearer test-yenkasa-ai-token"},
        )

    assert response.status_code == 200
    assert response.json()["registered_agents"][0] == "system"


def test_viewer_cannot_run_admin_database_query() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/agent/query",
            json={"query": "How many repo chunks exist?"},
            headers=VIEWER_HEADERS,
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient role."}


def test_explicit_database_agent_requires_admin_role() -> None:
    payload = AgentQueryRequest(query="How many repo chunks exist?", agent="DatabaseAgent")

    assert required_role_for_query(payload) == "admin"


def test_duplicate_api_key_keeps_highest_role() -> None:
    class FakeState:
        settings = Settings(
            admin_api_key="same-key",
            developer_api_key="same-key",
            viewer_api_key="same-key",
        )

    class FakeApp:
        state = FakeState()

    class FakeRequest:
        app = FakeApp()

    assert _configured_keys(FakeRequest()) == {"same-key": "admin"}


def test_oversized_query_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/agent/query",
            json={"query": "x" * 2001},
            headers=ADMIN_HEADERS,
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid request."}


def test_readiness_reports_unconfigured_external_services() -> None:
    with TestClient(app) as client:
        response = client.get("/ready", headers=ADMIN_HEADERS)

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert set(payload["checks"]) == {"mongodb", "vertex_ai", "cloud_run", "cloud_logging"}


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
        assert length in {1, None}
        return [{"repo_name": "yenkasaChat", "file_path": "app/main.py", "indexed_at": "2026-06-06T12:00:00Z"}]


class FakeLatestCollection:
    def find(self, filter_query: dict[str, object], projection: dict[str, int]) -> FakeLatestCursor:
        assert filter_query == {}
        assert projection["_id"] == 0
        return FakeLatestCursor()

    def aggregate(self, pipeline: list[dict[str, object]]) -> FakeLatestCursor:
        assert pipeline[-1]["$project"]["_id"] == 0
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
        assert name in {"ai_embeddings", "yme_memories"}
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
    assert response.result["top_repositories"] == [{"repository": "yenkasaChat", "chunk_count": 9}]
    assert response.result["evidence"]["database_agent_executed"] is True


class FakeSQLDatabaseInventoryRepository:
    async def inventory(self) -> dict[str, object]:
        return {
            "database": "yenkasa_store",
            "engine": "mysql",
            "configured": False,
        }


class FakeDatabaseInventoryRepository:
    def __init__(self) -> None:
        self.settings = Settings()

    def configured_databases(self) -> list[str]:
        return ["yenkasa_ai_db", "yenkasaChat"]

    async def list_collections(self, database_name: str | None = None) -> dict[str, object]:
        return {
            "collections": ["users", "posts", "comments"],
            "database": database_name,
            "evidence": {
                "agent": "DatabaseAgent",
                "database_agent_executed": True,
                "databases_scanned": 1 if database_name else 2,
                "collections_scanned": 3,
                "documents_analyzed": 0,
                "indexes_inspected": 0,
            },
        }

    async def collection_counts(self, database_name: str | None = None) -> dict[str, object]:
        return {
            "counts": {"yenkasaChat": {"users": 4120, "posts": 83912, "comments": 210001}},
            "evidence": {
                "agent": "DatabaseAgent",
                "database_agent_executed": True,
                "databases_scanned": 1,
                "collections_scanned": 3,
                "documents_analyzed": 298033,
                "indexes_inspected": 0,
            },
        }

    async def collection_indexes(
        self,
        *,
        collection_name: str | None = None,
        database_name: str | None = None,
    ) -> dict[str, object]:
        return {
            "indexes": {
                database_name or "yenkasaChat": {
                    collection_name or "posts": [
                        {"name": "_id_", "key": {"_id": 1}},
                        {"name": "authorId_1", "key": {"authorId": 1}},
                    ]
                }
            },
            "evidence": {
                "agent": "DatabaseAgent",
                "database_agent_executed": True,
                "databases_scanned": 1,
                "collections_scanned": 1,
                "documents_analyzed": 0,
                "indexes_inspected": 2,
            },
        }

    async def collections_missing_indexes(self, database_name: str | None = None) -> dict[str, object]:
        return {
            "collections_missing_indexes": [
                {
                    "database": database_name or "yenkasaChat",
                    "collection": "notifications",
                    "document_count": 1200,
                    "index_count": 1,
                }
            ],
            "evidence": {
                "agent": "DatabaseAgent",
                "database_agent_executed": True,
                "databases_scanned": 1,
                "collections_scanned": 4,
                "documents_analyzed": 1200,
                "indexes_inspected": 5,
            },
        }

    async def schema_inspection(
        self,
        *,
        collection_name: str | None = None,
        database_name: str | None = None,
        sample_size: int = 25,
    ) -> dict[str, object]:
        return {
            "schemas": {
                database_name or "yenkasaChat": {
                    collection_name or "users": {
                        "sample_size": sample_size,
                        "fields": {"email": {"types": ["str"], "nullable": False}},
                    }
                }
            },
            "evidence": {
                "agent": "DatabaseAgent",
                "database_agent_executed": True,
                "databases_scanned": 1,
                "collections_scanned": 1,
                "documents_analyzed": sample_size,
                "indexes_inspected": 0,
            },
        }

    async def explain(
        self,
        *,
        collection_name: str,
        filter_query: dict[str, object] | None = None,
        database_name: str | None = None,
    ) -> dict[str, object]:
        return {
            "database": database_name or "yenkasaChat",
            "collection": collection_name,
            "filter": filter_query or {},
            "explain": {"queryPlanner": {"winningPlan": {"stage": "IXSCAN"}}},
            "evidence": {
                "agent": "DatabaseAgent",
                "database_agent_executed": True,
                "databases_scanned": 1,
                "collections_scanned": 1,
                "documents_analyzed": 0,
                "indexes_inspected": 0,
            },
        }

    async def query_pattern_risks(self, *, query: str) -> dict[str, object]:
        return {
            "query_pattern_risks": [
                {
                    "file_path": "src/notifications/service.js",
                    "function_name": "loadNotifications",
                    "collection": "notifications",
                    "likely_failure_point": "Potential runtime exception where code assumes database fields exist.",
                    "confidence_score": 0.62,
                }
            ],
            "evidence": {
                "agent": "DatabaseAgent",
                "database_agent_executed": True,
                "databases_scanned": 2,
                "collections_scanned": 3,
                "documents_analyzed": 1,
                "indexes_inspected": 0,
            },
        }


def test_database_agent_routes_baleshop_sql_inventory() -> None:
    mongodb = FakeMongoDBService(collection=FakeAggregateCollection())
    agent = DatabaseAgent(
        repo_chunks_repository=RepoChunksRepository(mongodb),
        memory_embeddings_repository=MemoryEmbeddingsRepository(mongodb),
        sql_database_inventory_repository=FakeSQLDatabaseInventoryRepository(),
    )

    response = asyncio.run(agent.execute("Show yenkasa_store SQL database inventory", {}))

    assert response.agent == "DatabaseAgent"
    assert response.success is True
    assert response.result == {
        "sql_database_inventory": {
            "database": "yenkasa_store",
            "engine": "mysql",
            "configured": False,
        }
    }


def test_database_agent_lists_live_collections() -> None:
    mongodb = FakeMongoDBService()
    agent = DatabaseAgent(
        repo_chunks_repository=RepoChunksRepository(mongodb),
        memory_embeddings_repository=MemoryEmbeddingsRepository(mongodb),
        database_inventory_repository=FakeDatabaseInventoryRepository(),
    )

    response = asyncio.run(agent.execute("List every MongoDB collection", {}))

    assert response.success is True
    assert response.result["collections"] == ["users", "posts", "comments"]
    assert response.result["evidence"]["database_agent_executed"] is True


def test_database_agent_counts_documents_for_collections() -> None:
    mongodb = FakeMongoDBService()
    agent = DatabaseAgent(
        repo_chunks_repository=RepoChunksRepository(mongodb),
        memory_embeddings_repository=MemoryEmbeddingsRepository(mongodb),
        database_inventory_repository=FakeDatabaseInventoryRepository(),
    )

    response = asyncio.run(agent.execute("How many documents exist in each collection?", {}))

    assert response.success is True
    assert response.result["counts"]["yenkasaChat"]["posts"] == 83912
    assert response.result["evidence"]["documents_analyzed"] == 298033


def test_database_agent_shows_indexes_for_collection() -> None:
    mongodb = FakeMongoDBService()
    agent = DatabaseAgent(
        repo_chunks_repository=RepoChunksRepository(mongodb),
        memory_embeddings_repository=MemoryEmbeddingsRepository(mongodb),
        database_inventory_repository=FakeDatabaseInventoryRepository(),
    )

    response = asyncio.run(agent.execute("Show indexes for posts collection", {}))

    assert response.success is True
    assert "posts" in response.result["indexes"]["yenkasaChat"]
    assert response.result["evidence"]["indexes_inspected"] == 2


def test_database_agent_audits_schema_and_missing_indexes() -> None:
    mongodb = FakeMongoDBService()
    agent = DatabaseAgent(
        repo_chunks_repository=RepoChunksRepository(mongodb),
        memory_embeddings_repository=MemoryEmbeddingsRepository(mongodb),
        database_inventory_repository=FakeDatabaseInventoryRepository(),
    )

    response = asyncio.run(agent.execute("Audit schema for users collection", {"sample_size": 5}))

    assert response.success is True
    assert "schema_inspection" in response.result
    assert response.result["evidence"]["collections_scanned"] == 5


def test_database_agent_runtime_exception_hotspots_use_database_evidence() -> None:
    mongodb = FakeMongoDBService()
    agent = DatabaseAgent(
        repo_chunks_repository=RepoChunksRepository(mongodb),
        memory_embeddings_repository=MemoryEmbeddingsRepository(mongodb),
        database_inventory_repository=FakeDatabaseInventoryRepository(),
    )

    response = asyncio.run(agent.execute("Find runtime exception hotspots based on database usage", {}))

    assert response.success is True
    risks = response.result["database_health"]["query_pattern_risks"]
    assert risks[0]["file_path"] == "src/notifications/service.js"
    assert risks[0]["collection"] == "notifications"


class FakeRepositoryMongoDBService:
    async def aggregate(self, collection_name: str, pipeline: list[dict[str, object]]) -> list[dict[str, object]]:
        assert collection_name == "ai_embeddings"
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


class FakePostgresRepositoryStore:
    is_postgres_document_store = True

    async def count_documents(self, collection_name: str, filter_query: dict[str, object] | None = None) -> int:
        assert collection_name == "ai_embeddings"
        assert filter_query is None
        return 18848

    async def collection_stats(self, collection_name: str) -> dict[str, object]:
        assert collection_name == "ai_embeddings"
        return {"count": 18848, "storage_backend": "postgres", "table": "ai_documents"}

    async def repository_inventory(self, collection_name: str) -> list[dict[str, object]]:
        assert collection_name == "ai_embeddings"
        return [
            {
                "repository": "yenkasaChat",
                "chunk_count": 4123,
                "file_count": 1200,
                "latest_indexed_at": "2026-06-11T10:00:00Z",
            }
        ]

    async def top_repositories_by_chunk_count(
        self,
        collection_name: str,
        *,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        assert collection_name == "ai_embeddings"
        assert limit == 1
        return [{"repository": "YenkasaCodeAgent", "chunk_count": 13438}]

    async def language_breakdown(self, collection_name: str) -> list[dict[str, object]]:
        assert collection_name == "ai_embeddings"
        return [{"language": "python", "chunk_count": 100, "file_count": 20}]

    async def count_files_by_language(self, language: str, collection_name: str) -> dict[str, object]:
        assert collection_name == "ai_embeddings"
        assert language == "python"
        return {"language": "python", "chunk_count": 100, "file_count": 20}

    async def latest_indexed_file(self, collection_name: str) -> dict[str, object]:
        assert collection_name == "ai_embeddings"
        return {
            "repository": "YenkasaAI",
            "file_path": "backend/app/main.py",
            "indexed_at": "2026-06-11T10:00:00Z",
        }

    async def health_anomalies(self, collection_name: str) -> dict[str, object]:
        assert collection_name == "ai_embeddings"
        return {
            "missing_metadata_count": 0,
            "zero_chunk_repositories": [],
            "indexing_anomalies": [],
        }


class FakePostgresSearchStore(FakePostgresRepositoryStore):
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def search_repo_chunks_text(
        self,
        query: str,
        collection_name: str,
        *,
        limit: int = 5,
    ) -> list[dict[str, object]]:
        self.queries.append(query)
        assert collection_name == "ai_embeddings"
        assert limit == 5
        return [
            {
                "file_path": "Procfile",
                "repository": "yenkasaChat",
                "score": 4.0,
                "snippet": "web: node server.js",
            }
        ]


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


def test_repository_inventory_reads_postgres_document_store() -> None:
    store = FakePostgresRepositoryStore()
    agent = RepositoryAgent(
        repo_chunks_repository=RepoChunksRepository(store),
        repository_intelligence_repository=RepositoryIntelligenceRepository(store),
    )

    response = asyncio.run(agent.execute("Can you see my repo yenkasaChat?"))

    assert response.success is True
    assert response.result == {
        "repositories": [
            {
                "repository": "yenkasaChat",
                "chunk_count": 4123,
                "file_count": 1200,
                "latest_indexed_at": "2026-06-11T10:00:00Z",
            }
        ]
    }


def test_repository_agent_searches_indexed_content_for_file_questions() -> None:
    store = FakePostgresSearchStore()
    agent = RepositoryAgent(
        repo_chunks_repository=RepoChunksRepository(store),
        repository_intelligence_repository=RepositoryIntelligenceRepository(store),
    )

    response = asyncio.run(agent.execute("Which file handles Cloudinary uploads in yenkasaChat?"))

    assert store.queries == ["Which file handles Cloudinary uploads in yenkasaChat?"]
    assert response.success is True
    assert response.result == {
        "matches": [
            {
                "file_path": "Procfile",
                "repository": "yenkasaChat",
                "similarity_score": 4.0,
                "snippet": "web: node server.js",
            }
        ],
        "search": {
            "query": "Which file handles Cloudinary uploads in yenkasaChat?",
            "collection": "ai_embeddings",
            "match_count": 1,
        },
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
    response = asyncio.run(
        orchestrator.route(AgentQueryRequest(query="Show repository inventory", agent="RepositoryAgent"))
    )

    assert response.agent == "RepositoryAgent"
    assert response.success is True


def test_repository_agent_routing_uses_postgres_repository_store() -> None:
    orchestrator = YenkasaCodeOrchestrator(
        mongodb=FakeRepositoryMongoDBService(),
        repository_store=FakePostgresRepositoryStore(),
    )
    response = asyncio.run(
        orchestrator.route(AgentQueryRequest(query="Show largest repository by chunk count", agent="RepositoryAgent", context={"limit": 1}))
    )

    assert response.agent == "RepositoryAgent"
    assert response.success is True
    assert response.result["answer"] == "The largest indexed repository is YenkasaCodeAgent with 13,438 chunks."
    assert response.result["facts"] == {"top_repositories": [{"repository": "YenkasaCodeAgent", "chunk_count": 13438}]}
    assert "raw_evidence" not in response.result
    assert response.evidence_package["agent"] == "RepositoryAgent"


def test_repository_agent_routing_finalizes_content_search_answer() -> None:
    store = FakePostgresSearchStore()
    orchestrator = YenkasaCodeOrchestrator(
        mongodb=FakeRepositoryMongoDBService(),
        repository_store=store,
    )
    response = asyncio.run(
        orchestrator.route(AgentQueryRequest(query="are you aware am hosting my call and video call server on heroku? check my repo", agent="RepositoryAgent"))
    )

    assert store.queries == ["are you aware am hosting my call and video call server on heroku? check my repo"]
    assert response.agent == "RepositoryAgent"
    assert response.success is True
    assert "I searched the indexed repository content" in response.result["answer"]
    assert "yenkasaChat Procfile" in response.result["answer"]
    assert response.result["sources"][0]["file_path"] == "Procfile"


class FakeEmbeddingService:
    async def embed_query(self, text: str) -> list[float]:
        assert text
        return [0.1, 0.2, 0.3]


class FakeVectorMongoDBService:
    async def aggregate(self, collection_name: str, pipeline: list[dict[str, object]]) -> list[dict[str, object]]:
        if "$vectorSearch" in pipeline[0]:
            assert pipeline[0]["$vectorSearch"]["queryVector"] == [0.1, 0.2, 0.3]
            if collection_name == "yme_memories":
                return [
                    {
                        "file_path": None,
                        "repository": "yenkasaChat",
                        "score": 0.91,
                        "snippet": "User memory about authentication decisions.",
                    }
                ]
            assert collection_name == "ai_embeddings"
            return [
                {
                    "file_path": "backend/auth/jwt.py",
                    "repository": "yenkasaChat",
                    "score": 0.94,
                    "snippet": "def verify_jwt(token): ...",
                }
            ]
        assert collection_name == "ai_embeddings"
        pipeline_text = str(pipeline)
        if "latest_indexed_at" in pipeline_text:
            return [{"repository": "yenkasaChat", "chunk_count": 20, "file_count": 4}]
        return [{"repository": "yenkasaChat", "chunk_count": 20}]


def build_vector_search_agent(mongodb: FakeVectorMongoDBService | None = None) -> VectorSearchAgent:
    return VectorSearchAgent(
        embedding_service=FakeEmbeddingService(),
        vector_search_repository=VectorSearchRepository(mongodb or FakeVectorMongoDBService()),
    )


def test_vector_semantic_search() -> None:
    response = asyncio.run(build_vector_search_agent().execute("Find JWT authentication"))

    assert response.agent == "VectorSearchAgent"
    assert response.success is True
    assert response.result == {
        "matches": [
            {
                "file_path": "backend/auth/jwt.py",
                "repository": "yenkasaChat",
                "similarity_score": 0.94,
                "snippet": "def verify_jwt(token): ...",
            }
        ]
    }


def test_vector_architecture_search() -> None:
    response = asyncio.run(build_vector_search_agent().execute("Find post approval workflow"))

    assert response.success is True
    assert response.result["matches"][0]["repository"] == "yenkasaChat"
    assert response.result["matches"][0]["file_path"] == "backend/auth/jwt.py"


def test_vector_memory_search() -> None:
    response = asyncio.run(build_vector_search_agent().execute("Find related memories"))

    assert response.success is True
    assert response.result == {
        "matches": [
            {
                "file_path": None,
                "repository": "yenkasaChat",
                "similarity_score": 0.91,
                "snippet": "User memory about authentication decisions.",
            }
        ]
    }


def test_vector_repo_search_uses_postgres_repository_store_when_available() -> None:
    store = FakePostgresSearchStore()
    response = asyncio.run(
        VectorSearchAgent(
            embedding_service=FakeEmbeddingService(),
            vector_search_repository=VectorSearchRepository(store, memory_store=FakeVectorMongoDBService()),
        ).execute("are you hosting the call server on Heroku?")
    )

    assert store.queries == ["are you hosting the call server on Heroku?"]
    assert response.success is True
    assert response.result == {
        "matches": [
            {
                "file_path": "Procfile",
                "repository": "yenkasaChat",
                "similarity_score": 4.0,
                "snippet": "web: node server.js",
            }
        ]
    }


def test_vector_memory_search_stays_on_mongodb_when_repo_store_is_postgres() -> None:
    response = asyncio.run(
        VectorSearchAgent(
            embedding_service=FakeEmbeddingService(),
            vector_search_repository=VectorSearchRepository(FakePostgresSearchStore(), memory_store=FakeVectorMongoDBService()),
        ).execute("Find related memories")
    )

    assert response.success is True
    assert response.result["matches"][0]["snippet"] == "User memory about authentication decisions."


def test_vector_search_routing_behavior() -> None:
    orchestrator = YenkasaCodeOrchestrator(
        mongodb=FakeVectorMongoDBService(),
        embedding_service=FakeEmbeddingService(),
    )
    response = asyncio.run(
        orchestrator.route(AgentQueryRequest(query="Find login implementation", agent="VectorSearchAgent"))
    )

    assert response.agent == "VectorSearchAgent"
    assert response.success is True


class FakeAuditDependencyAgent:
    name = "fake"

    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.queries: list[str] = []

    async def execute(self, query: str, context: dict[str, object] | None = None):
        self.queries.append(query)
        return type(
            "FakeResponse",
            (),
            {
                "agent": self.name,
                "success": True,
                "result": self.result,
                "error": None,
            },
        )()


def build_code_audit_agent(
    *,
    vector_result: dict[str, object] | None = None,
    repository_result: dict[str, object] | None = None,
    database_result: dict[str, object] | None = None,
) -> CodeAuditAgent:
    vector_agent = FakeAuditDependencyAgent(
        vector_result
        or {
            "matches": [
                {
                    "file_path": "app/config.py",
                    "repository": "yenkasaChat",
                    "similarity_score": 0.95,
                    "snippet": "API_KEY = 'secret-token'",
                }
            ]
        }
    )
    repository_agent = FakeAuditDependencyAgent(
        repository_result
        or {
            "repositories": [
                {
                    "repository": "yenkasaChat",
                    "chunk_count": 800,
                    "file_count": 120,
                }
            ]
        }
    )
    database_agent = FakeAuditDependencyAgent(
        database_result
        or {
            "top_repositories": [
                {
                    "repository": "yenkasaChat",
                    "chunk_count": 800,
                }
            ]
        }
    )
    return CodeAuditAgent(
        AuditService(
            database_agent=database_agent,
            repository_agent=repository_agent,
            vector_search_agent=vector_agent,
        )
    )


def test_code_audit_security_audit() -> None:
    response = asyncio.run(build_code_audit_agent().execute("Security audit yenkasaChat"))

    assert response.agent == "CodeAuditAgent"
    assert response.success is True
    assert response.result["findings"][0]["severity"] == "HIGH"
    assert response.result["findings"][0]["category"] == "Security"


def test_code_audit_architecture_audit() -> None:
    response = asyncio.run(
        build_code_audit_agent(
            vector_result={
                "matches": [
                    {
                        "file_path": "app/services/user.py",
                        "repository": "yenkasaChat",
                        "similarity_score": 0.87,
                        "snippet": "duplicate responsibilities across user service and profile service",
                    }
                ]
            }
        ).execute("Architecture audit YME")
    )

    categories = {finding["category"] for finding in response.result["findings"]}
    assert response.success is True
    assert "Architecture" in categories


def test_code_audit_api_audit() -> None:
    response = asyncio.run(
        build_code_audit_agent(
            vector_result={
                "matches": [
                    {
                        "file_path": "app/routes/auth.py",
                        "repository": "yenkasaChat",
                        "similarity_score": 0.9,
                        "snippet": "router.post('/login') request body without validation response varies",
                    }
                ]
            }
        ).execute("API audit")
    )

    assert response.success is True
    assert response.result["findings"][0]["category"] == "API"
    assert response.result["findings"][0]["severity"] == "MEDIUM"


def test_code_audit_code_quality_audit() -> None:
    response = asyncio.run(
        build_code_audit_agent(
            vector_result={
                "matches": [
                    {
                        "file_path": "app/jobs/sync.py",
                        "repository": "yenkasaChat",
                        "similarity_score": 0.88,
                        "snippet": "TODO duplicate logic missing error handling",
                    }
                ]
            }
        ).execute("Code quality audit")
    )

    categories = {finding["category"] for finding in response.result["findings"]}
    assert response.success is True
    assert "Code Quality" in categories


def test_code_audit_routing_behavior() -> None:
    orchestrator = YenkasaCodeOrchestrator(
        mongodb=FakeVectorMongoDBService(),
        embedding_service=FakeEmbeddingService(),
    )
    response = asyncio.run(
        orchestrator.route(AgentQueryRequest(query="Find issues in yenkasaChat", agent="CodeAuditAgent"))
    )

    assert response.agent == "CodeAuditAgent"
    assert response.success is True


def build_refactor_agent(
    *,
    audit_result: dict[str, object] | None = None,
    repository_result: dict[str, object] | None = None,
    vector_result: dict[str, object] | None = None,
) -> RefactorAgent:
    audit_agent = FakeAuditDependencyAgent(
        audit_result
        or {
            "findings": [
                {
                    "severity": "HIGH",
                    "category": "Architecture",
                    "issue": "Oversized module mixes routing, data access, and business logic.",
                    "recommendation": "Split responsibilities into route, service, and repository layers.",
                }
            ]
        }
    )
    repository_agent = FakeAuditDependencyAgent(
        repository_result
        or {
            "repositories": [
                {
                    "repository": "yenkasaChat",
                    "chunk_count": 900,
                    "file_count": 150,
                }
            ]
        }
    )
    vector_agent = FakeAuditDependencyAgent(
        vector_result
        or {
            "matches": [
                {
                    "file_path": "app/services/user.py",
                    "repository": "yenkasaChat",
                    "similarity_score": 0.9,
                    "snippet": "duplicate service responsibility and repeated business logic",
                }
            ]
        }
    )
    return RefactorAgent(
        RefactorService(
            code_audit_agent=audit_agent,
            repository_agent=repository_agent,
            vector_search_agent=vector_agent,
        )
    )


def test_refactor_technical_debt_analysis() -> None:
    response = asyncio.run(build_refactor_agent().execute("Show technical debt"))

    assert response.agent == "RefactorAgent"
    assert response.success is True
    assert response.result["recommendations"][0]["priority"] == "HIGH"
    assert response.result["recommendations"][0]["risk"] == "MEDIUM"


def test_refactor_duplication_analysis() -> None:
    response = asyncio.run(build_refactor_agent().execute("Find duplicated code blocks"))

    assert response.success is True
    assert response.result["recommendations"][0]["category"] == "Duplication"
    assert response.result["recommendations"][0]["risk"] == "LOW"


def test_refactor_service_extraction_recommendations() -> None:
    response = asyncio.run(build_refactor_agent().execute("Extract service from oversized controllers"))

    categories = {recommendation["category"] for recommendation in response.result["recommendations"]}
    assert response.success is True
    assert "Service Extraction" in categories


def test_refactor_dependency_analysis() -> None:
    response = asyncio.run(
        build_refactor_agent(
            vector_result={
                "matches": [
                    {
                        "file_path": "app/services/a.py",
                        "repository": "yenkasaChat",
                        "similarity_score": 0.86,
                        "snippet": "circular dependency import coupling hotspot",
                    }
                ]
            }
        ).execute("Analyze dependency hotspots")
    )

    assert response.success is True
    assert response.result["recommendations"][0]["category"] == "Dependency"
    assert response.result["recommendations"][0]["priority"] == "HIGH"


def test_refactor_routing_behavior() -> None:
    orchestrator = YenkasaCodeOrchestrator(
        mongodb=FakeVectorMongoDBService(),
        embedding_service=FakeEmbeddingService(),
    )
    response = asyncio.run(
        orchestrator.route(AgentQueryRequest(query="Reduce technical debt in yenkasaChat", agent="RefactorAgent"))
    )

    assert response.agent == "RefactorAgent"
    assert response.success is True


class FakeCloudRunService:
    async def service_status(self) -> dict[str, object]:
        return {
            "service": "yenkasa-ai",
            "url": "https://yenkasa-ai.example.run.app",
            "latest_ready_revision": "yenkasa-ai-00012",
            "latest_created_revision": "yenkasa-ai-00013",
            "traffic": [{"revision": "yenkasa-ai-00012", "percent": 100, "tag": None}],
            "healthy": True,
        }

    async def revision_status(self) -> dict[str, object]:
        return {
            "service": "yenkasa-ai",
            "live_revision": "yenkasa-ai-00012",
            "latest_ready_revision": "yenkasa-ai-00012",
            "latest_created_revision": "yenkasa-ai-00013",
        }

    async def traffic_allocation(self) -> dict[str, object]:
        return {"service": "yenkasa-ai", "traffic": [{"revision": "yenkasa-ai-00012", "percent": 100}]}

    async def deployment_history(self) -> dict[str, object]:
        return {
            "service": "yenkasa-ai",
            "revisions": [
                {"revision": "yenkasa-ai-00012", "state": "READY"},
                {"revision": "yenkasa-ai-00013", "state": "CREATED"},
            ],
        }

    async def deployment_health(self) -> dict[str, object]:
        return {"service": "yenkasa-ai", "healthy": True, "latest_ready_revision": "yenkasa-ai-00012"}


class FakeObservabilityService:
    async def error_summary(self, *, query: str, hours: int = 24) -> dict[str, object]:
        return {
            "window_hours": hours,
            "error_count": 2,
            "errors": [
                {"severity": "ERROR", "message": "login failed: invalid token"},
                {"severity": "ERROR", "message": "login failed: timeout"},
            ],
            "incident_detected": False,
        }

    async def log_summary(self, *, query: str, hours: int = 24) -> dict[str, object]:
        return {
            "window_hours": hours,
            "log_count": 1,
            "logs": [{"severity": "INFO", "message": "notification sent"}],
        }

    async def performance_metrics(self, *, query: str, hours: int = 24) -> dict[str, object]:
        return {"window_hours": hours, "request_count": 10, "slow_request_indicators": 1}

    async def request_trends(self, *, query: str, hours: int = 24) -> dict[str, object]:
        return {"window_hours": hours, "request_count": 10, "trend": "activity_detected"}

    async def incident_detection(self, *, query: str, hours: int = 24) -> dict[str, object]:
        return {"incident_detected": True, "error_count": 8, "signals": []}


def test_cloudrun_service_status() -> None:
    response = asyncio.run(CloudRunAgent(FakeCloudRunService()).execute("Show Cloud Run status"))

    assert response.agent == "CloudRunAgent"
    assert response.success is True
    assert response.result["service_status"]["healthy"] is True
    assert response.result["service_status"]["latest_ready_revision"] == "yenkasa-ai-00012"


def test_cloudrun_revision_retrieval() -> None:
    response = asyncio.run(CloudRunAgent(FakeCloudRunService()).execute("Which revision is live?"))

    assert response.success is True
    assert response.result == {
        "revision_status": {
            "service": "yenkasa-ai",
            "live_revision": "yenkasa-ai-00012",
            "latest_ready_revision": "yenkasa-ai-00012",
            "latest_created_revision": "yenkasa-ai-00013",
        }
    }


def test_cloudrun_deployment_history() -> None:
    response = asyncio.run(CloudRunAgent(FakeCloudRunService()).execute("Show deployment history"))

    assert response.success is True
    assert response.result["deployment_history"]["revisions"][0]["state"] == "READY"


def test_observability_error_summary() -> None:
    response = asyncio.run(ObservabilityAgent(FakeObservabilityService()).execute("Why is login failing?"))

    assert response.agent == "ObservabilityAgent"
    assert response.success is True
    assert response.result["error_summary"]["error_count"] == 2


def test_observability_log_summary() -> None:
    response = asyncio.run(ObservabilityAgent(FakeObservabilityService()).execute("Show recent backend logs"))

    assert response.success is True
    assert response.result == {
        "log_summary": {
            "window_hours": 24,
            "log_count": 1,
            "logs": [{"severity": "INFO", "message": "notification sent"}],
        }
    }


def test_cloudrun_and_observability_routing() -> None:
    orchestrator = YenkasaCodeOrchestrator(
        mongodb=FakeVectorMongoDBService(),
        embedding_service=FakeEmbeddingService(),
        cloudrun_service=FakeCloudRunService(),
        observability_service=FakeObservabilityService(),
    )
    cloudrun_response = asyncio.run(
        orchestrator.route(AgentQueryRequest(query="Show deployment history", agent="CloudRunAgent"))
    )
    observability_response = asyncio.run(
        orchestrator.route(AgentQueryRequest(query="Show recent backend errors", agent="ObservabilityAgent"))
    )

    assert cloudrun_response.agent == "CloudRunAgent"
    assert cloudrun_response.success is True
    assert observability_response.agent == "ObservabilityAgent"
    assert observability_response.success is True


class FakeYioAgent:
    def __init__(self, name: str, result: dict[str, object], success: bool = True, error: str | None = None) -> None:
        self.name = name
        self.description = f"Fake {name}"
        self.capabilities = []
        self.result = result
        self.success = success
        self.error = error
        self.queries: list[str] = []

    def descriptor(self):
        return {"name": self.name, "description": self.description, "capabilities": self.capabilities}

    async def execute(self, query: str, context: dict[str, object] | None = None) -> AgentResponse:
        self.queries.append(query)
        return AgentResponse(agent=self.name, success=self.success, result=dict(self.result), error=self.error)


def build_yio_registry(*agents: FakeYioAgent) -> AgentRegistry:
    registry = AgentRegistry()
    for agent in agents:
        registry.register(agent)
    return registry


def test_yio_single_agent_routing() -> None:
    registry = build_yio_registry(
        FakeYioAgent("ObservabilityAgent", {"findings": [{"category": "Errors", "issue": "Login failures"}]})
    )
    response = asyncio.run(YenkasaIntelligenceOrchestrator(registry=registry).execute(query="Show recent backend errors"))

    assert response.agent == "YIO"
    assert response.success is True
    assert response.result["plan"]["agents"] == ["ObservabilityAgent"]
    assert response.result["findings"][0]["issue"] == "Login failures"


def test_yio_multi_agent_planning() -> None:
    classifier = IntentClassifier()
    planner = ExecutionPlanner()

    intents = classifier.classify("Audit notifications and check deployment health.")
    plan = planner.plan(query="Audit notifications and check deployment health.", intents=intents)

    assert "multi-agent" in intents
    assert [step.agent for step in plan.steps] == [
        "VectorSearchAgent",
        "RepositoryAgent",
        "CodeAuditAgent",
        "CloudRunAgent",
        "ObservabilityAgent",
    ]


def test_yio_routes_store_database_queries_to_database_agent() -> None:
    classifier = IntentClassifier()
    planner = ExecutionPlanner()

    intents = classifier.classify("Show yenkasa_store SQL database inventory.")
    plan = planner.plan(query="Show yenkasa_store SQL database inventory.", intents=intents)

    assert intents == ["database"]
    assert [step.agent for step in plan.steps] == ["DatabaseAgent"]


def test_yio_routes_yenkasa_app_context_to_repository_agent_without_repo_keyword() -> None:
    classifier = IntentClassifier()
    planner = ExecutionPlanner()

    intents = classifier.classify("Tell me what is happening in the Yenkasa app.")
    plan = planner.plan(query="Tell me what is happening in the Yenkasa app.", intents=intents)

    assert "repository" in intents
    assert "RepositoryAgent" in [step.agent for step in plan.steps]


def test_yio_routes_yenkasa_app_bug_questions_to_repository_search_and_audit() -> None:
    classifier = IntentClassifier()
    planner = ExecutionPlanner()

    intents = classifier.classify("Find and fix the notification bug in the Yenkasa app.")
    plan = planner.plan(query="Find and fix the notification bug in the Yenkasa app.", intents=intents)

    assert "multi-agent" in intents
    assert "repository" in intents
    assert "search" in intents
    assert "audit" in intents
    assert {"RepositoryAgent", "VectorSearchAgent", "CodeAuditAgent"}.issubset(
        {step.agent for step in plan.steps}
    )


def test_yio_routes_repo_hosting_questions_to_repository_search() -> None:
    classifier = IntentClassifier()
    planner = ExecutionPlanner()

    query = "are you aware am hosting my call and video call server on heroku ?check my repo"
    intents = classifier.classify(query)
    plan = planner.plan(query=query, intents=intents)

    assert "multi-agent" in intents
    assert "repository" in intents
    assert "search" in intents
    assert "RepositoryAgent" in [step.agent for step in plan.steps]
    assert "VectorSearchAgent" in [step.agent for step in plan.steps]


def test_yio_reasoning_uses_source_matches_for_repo_hosting_questions() -> None:
    response = AgentResponse(
        agent="YIO",
        success=True,
        result={
            "evidence": [
                {
                    "agent": "RepositoryAgent",
                    "facts": {
                        "repository_count": 12,
                        "repository_names": ["yenkasaChat", "YenkasaCodeAgent"],
                        "total_files": 4792,
                        "total_chunks": 18848,
                        "latest_repository": {
                            "repository": "YenkasaCodeAgent",
                            "latest_indexed_at": "2026-06-08T00:04:57.773729",
                        },
                    },
                    "sources": [],
                    "confidence": 0.96,
                },
                {
                    "agent": "VectorSearchAgent",
                    "repository": "yenkasaChat",
                    "file_path": "Procfile",
                    "snippet": "web: npm start",
                    "similarity_score": 0.91,
                },
                {
                    "agent": "VectorSearchAgent",
                    "repository": "yenkasaChat",
                    "file_path": "src/signaling/server.js",
                    "snippet": "const io = require('socket.io')(server);",
                    "similarity_score": 0.88,
                },
            ],
            "plan": {"agents": ["RepositoryAgent", "VectorSearchAgent"]},
            "agent_results": [
                {
                    "agent": "RepositoryAgent",
                    "facts": {
                        "repository_count": 12,
                        "repository_names": ["yenkasaChat", "YenkasaCodeAgent"],
                        "total_files": 4792,
                        "total_chunks": 18848,
                    },
                    "sources": [],
                    "confidence": 0.96,
                },
                {
                    "agent": "VectorSearchAgent",
                    "facts": {"match_count": 2},
                    "sources": [
                        {
                            "repository": "yenkasaChat",
                            "file_path": "Procfile",
                            "snippet": "web: npm start",
                            "score": 0.91,
                        }
                    ],
                    "confidence": 0.96,
                },
            ],
        },
    )

    finalized = ReasoningEngine().finalize_response(
        query="are you aware am hosting my call and video call server on heroku ?check my repo",
        response=response,
    )

    assert "file-level evidence" in finalized.result["answer"]
    assert "yenkasaChat Procfile" in finalized.result["answer"]
    assert "src/signaling/server.js" in finalized.result["answer"]
    assert "I collected evidence" not in finalized.result["answer"]
    assert "Selected agents" not in finalized.result["answer"]


def test_yio_reasoning_reports_zero_source_matches_without_raw_inventory_dump() -> None:
    response = AgentResponse(
        agent="YIO",
        success=True,
        result={
            "evidence": [
                {
                    "agent": "RepositoryAgent",
                    "facts": {
                        "repository_count": 12,
                        "repository_names": ["yenkasaChat", "YenkasaCodeAgent"],
                        "total_files": 4792,
                        "total_chunks": 18848,
                        "latest_repository": {
                            "repository": "YenkasaCodeAgent",
                            "latest_indexed_at": "2026-06-08T00:04:57.773729",
                        },
                    },
                    "sources": [],
                    "confidence": 0.96,
                }
            ],
            "plan": {"agents": ["RepositoryAgent", "VectorSearchAgent"]},
            "agent_results": [
                {
                    "agent": "RepositoryAgent",
                    "facts": {
                        "repository_count": 12,
                        "repository_names": ["yenkasaChat", "YenkasaCodeAgent"],
                        "total_files": 4792,
                        "total_chunks": 18848,
                        "latest_repository": {
                            "repository": "YenkasaCodeAgent",
                            "latest_indexed_at": "2026-06-08T00:04:57.773729",
                        },
                    },
                    "sources": [],
                    "confidence": 0.96,
                },
                {
                    "agent": "VectorSearchAgent",
                    "facts": {"match_count": 0},
                    "sources": [],
                    "confidence": 0.96,
                },
            ],
        },
    )

    finalized = ReasoningEngine().finalize_response(
        query="are you aware am hosting my call and video call server on heroku ?check my repo",
        response=response,
    )

    answer = finalized.result["answer"]
    assert "I also ran source search" in answer
    assert "returned no file-level matches" in answer
    assert "must be paired with VectorSearchAgent" not in answer
    assert "Selected agents" not in answer


def test_yio_reasoning_distinguishes_call_server_files_from_heroku_hosting_evidence() -> None:
    response = AgentResponse(
        agent="YIO",
        success=True,
        result={
            "evidence": [
                {
                    "agent": "RepositoryAgent",
                    "facts": {
                        "repository_count": 12,
                        "repository_names": ["YenkasaChatSignaling"],
                        "total_files": 4792,
                        "total_chunks": 18848,
                    },
                    "sources": [],
                    "confidence": 0.96,
                },
                {
                    "agent": "VectorSearchAgent",
                    "repository": "YenkasaChatSignaling",
                    "file_path": "caller.server.js",
                    "snippet": "const WebSocket = require('ws'); data: { type: 'call_request', isVideo: true }",
                    "similarity_score": 7.0,
                },
            ],
            "plan": {"agents": ["RepositoryAgent", "VectorSearchAgent"]},
            "agent_results": [
                {
                    "agent": "RepositoryAgent",
                    "facts": {
                        "repository_count": 12,
                        "repository_names": ["YenkasaChatSignaling"],
                        "total_files": 4792,
                        "total_chunks": 18848,
                    },
                    "sources": [],
                    "confidence": 0.96,
                },
                {
                    "agent": "VectorSearchAgent",
                    "facts": {"match_count": 1},
                    "sources": [
                        {
                            "repository": "YenkasaChatSignaling",
                            "file_path": "caller.server.js",
                            "snippet": "const WebSocket = require('ws'); data: { type: 'call_request', isVideo: true }",
                            "score": 7.0,
                        }
                    ],
                    "confidence": 0.96,
                },
            ],
        },
    )

    finalized = ReasoningEngine().finalize_response(
        query="are you aware am hosting my call and video call server on heroku ?check my repo",
        response=response,
    )

    answer = finalized.result["answer"]
    assert "call/video-call server code" in answer
    assert "did not find file-level evidence that it is hosted on Heroku" in answer
    assert "YenkasaChatSignaling caller.server.js" in answer


def test_yio_routes_database_metadata_queries_to_database_agent() -> None:
    classifier = IntentClassifier()
    planner = ExecutionPlanner()

    for query in (
        "List collections",
        "Count documents in collections",
        "Show indexes for posts collection",
        "Audit schema",
        "Find slow queries",
        "Database performance",
        "Runtime exceptions",
        "Database health",
        "Collection statistics",
    ):
        intents = classifier.classify(query)
        plan = planner.plan(query=query, intents=intents)

        assert "database" in intents
        assert "DatabaseAgent" in [step.agent for step in plan.steps]


def test_yio_response_synthesis() -> None:
    plan = ExecutionPlanner().plan(query="Audit notifications.", intents=["audit"])
    result = ResponseSynthesizer().synthesize(
        query="Audit notifications.",
        plan=plan,
        responses=[
            AgentResponse(agent="CodeAuditAgent", success=True, result={"findings": [{"category": "Security"}]}),
            AgentResponse(
                agent="VectorSearchAgent",
                success=True,
                result={"matches": [{"file_path": "notifications.py", "repository": "yenkasaChat"}]},
            ),
            AgentResponse(
                agent="RefactorAgent",
                success=True,
                result={"recommendations": [{"category": "Architecture"}]},
            ),
        ],
    )

    assert result["findings"] == [{"category": "Security"}]
    assert result["recommendations"] == [{"category": "Architecture"}]
    assert result["evidence"][0]["file_path"] == "notifications.py"


def test_yio_execution_failures() -> None:
    registry = build_yio_registry(
        FakeYioAgent("CloudRunAgent", {}, success=False, error="Cloud Run unavailable")
    )
    response = asyncio.run(YenkasaIntelligenceOrchestrator(registry=registry).execute(query="Analyze deployment health."))

    assert response.agent == "YIO"
    assert response.success is False
    assert response.error == "One or more planned agents failed."
    assert response.result["findings"][0]["category"] == "Execution"


def build_product_builder_agent() -> ProductBuilderAgent:
    return ProductBuilderAgent(ProductBuilderService())


def test_product_builder_flutter_generation() -> None:
    response = asyncio.run(build_product_builder_agent().execute("Generate Flutter screen for login"))

    assert response.agent == "ProductBuilderAgent"
    assert response.success is True
    assert response.result["generation_type"] == "flutter"
    assert response.result["generated_files"][0]["kind"] == "screen"


def test_product_builder_fastapi_generation() -> None:
    response = asyncio.run(build_product_builder_agent().execute("Create API with FastAPI router and schema"))

    assert response.success is True
    assert response.result["generation_type"] == "fastapi"
    assert {item["kind"] for item in response.result["generated_files"]} == {"router", "schema"}


def test_product_builder_nodejs_generation() -> None:
    response = asyncio.run(build_product_builder_agent().execute("Generate Node.js routes and controller"))

    assert response.success is True
    assert response.result["generation_type"] == "nodejs"
    assert response.result["generated_files"][0]["path"].endswith(".routes.js")


def test_product_builder_schema_generation() -> None:
    response = asyncio.run(build_product_builder_agent().execute("Create schema and indexes for MongoDB"))

    assert response.success is True
    assert response.result["generation_type"] == "mongodb"
    assert {item["kind"] for item in response.result["generated_files"]} == {"mongodb_schema", "index"}


def test_product_builder_documentation_generation() -> None:
    response = asyncio.run(build_product_builder_agent().execute("Generate README and architecture documentation"))

    assert response.success is True
    assert response.result["generation_type"] == "docs"
    assert response.result["generated_files"][0]["path"] == "README.generated.md"


def test_product_builder_yio_routing() -> None:
    orchestrator = YenkasaCodeOrchestrator(
        mongodb=FakeVectorMongoDBService(),
        embedding_service=FakeEmbeddingService(),
        cloudrun_service=FakeCloudRunService(),
        observability_service=FakeObservabilityService(),
    )
    response = asyncio.run(orchestrator.route(AgentQueryRequest(query="Generate Flutter screen for onboarding")))

    assert response.agent == "YIO"
    assert response.success is True
    assert response.result["plan"]["agents"] == ["ProductBuilderAgent"]
    assert response.result["evidence"][0]["facts"]["generation_type"] == "flutter"
