from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app.agents.cloudrun_agent import CloudRunAgent
from app.agents.code_audit_agent import CodeAuditAgent
from app.agents.database_agent import DatabaseAgent
from app.agents.observability_agent import ObservabilityAgent
from app.agents.refactor_agent import RefactorAgent
from app.agents.repository_agent import RepositoryAgent
from app.agents.vector_search_agent import VectorSearchAgent
from app.config.settings import Settings
from app.core.orchestrator import YenkasaCodeOrchestrator
from app.main import app
from app.models.agent import AgentQueryRequest
from app.repositories.memory_embeddings_repository import MemoryEmbeddingsRepository
from app.repositories.repo_chunks_repository import RepoChunksRepository
from app.repositories.repository_intelligence_repository import RepositoryIntelligenceRepository
from app.repositories.vector_search_repository import VectorSearchRepository
from app.services.audit_service import AuditService
from app.services.cloudrun_service import CloudRunService
from app.services.mongodb_service import MongoDBService
from app.services.observability_service import ObservabilityService
from app.services.refactor_service import RefactorService


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    payload = response.json()
    assert payload == {
        "status": "ok",
        "version": "0.1.0",
        "registered_agents": 8,
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
    assert payload[3]["name"] == "VectorSearchAgent"
    assert payload[4]["name"] == "CodeAuditAgent"
    assert payload[5]["name"] == "RefactorAgent"
    assert payload[6]["name"] == "CloudRunAgent"
    assert payload[7]["name"] == "ObservabilityAgent"


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
    ]


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


class FakeEmbeddingService:
    async def embed_query(self, text: str) -> list[float]:
        assert text
        return [0.1, 0.2, 0.3]


class FakeVectorMongoDBService:
    async def aggregate(self, collection_name: str, pipeline: list[dict[str, object]]) -> list[dict[str, object]]:
        if "$vectorSearch" in pipeline[0]:
            assert pipeline[0]["$vectorSearch"]["queryVector"] == [0.1, 0.2, 0.3]
            if collection_name == "memory_embeddings":
                return [
                    {
                        "file_path": None,
                        "repository": "yenkasaChat",
                        "score": 0.91,
                        "snippet": "User memory about authentication decisions.",
                    }
                ]
            assert collection_name == "repo_chunks"
            return [
                {
                    "file_path": "backend/auth/jwt.py",
                    "repository": "yenkasaChat",
                    "score": 0.94,
                    "snippet": "def verify_jwt(token): ...",
                }
            ]
        assert collection_name == "repo_chunks"
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


def test_vector_search_routing_behavior() -> None:
    orchestrator = YenkasaCodeOrchestrator(
        mongodb=FakeVectorMongoDBService(),
        embedding_service=FakeEmbeddingService(),
    )
    response = asyncio.run(orchestrator.route(AgentQueryRequest(query="Find login implementation")))

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
    response = asyncio.run(orchestrator.route(AgentQueryRequest(query="Find issues in yenkasaChat")))

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
    response = asyncio.run(orchestrator.route(AgentQueryRequest(query="Reduce technical debt in yenkasaChat")))

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
    cloudrun_response = asyncio.run(orchestrator.route(AgentQueryRequest(query="Show deployment history")))
    observability_response = asyncio.run(orchestrator.route(AgentQueryRequest(query="Show recent backend errors")))

    assert cloudrun_response.agent == "CloudRunAgent"
    assert cloudrun_response.success is True
    assert observability_response.agent == "ObservabilityAgent"
    assert observability_response.success is True
