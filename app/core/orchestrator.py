from __future__ import annotations

import logging
import time

from app.agents import AgentRegistry
from app.agents import CloudRunAgent
from app.agents import CodeAuditAgent
from app.agents import DatabaseAgent
from app.agents import ObservabilityAgent
from app.agents import ProductBuilderAgent
from app.agents import RefactorAgent
from app.agents import RepositoryAgent
from app.agents import SystemAgent
from app.agents import VectorSearchAgent
from app.core.logging import log_structured
from app.models.agent import AgentDescriptor
from app.models.agent import AgentQueryRequest
from app.models.agent import AgentResponse
from app.models.metrics import AgentMetricsResponse
from app.orchestrator import YenkasaIntelligenceOrchestrator
from app.orchestrator.reasoning_engine import ReasoningEngine
from app.repositories import MemoryEmbeddingsRepository
from app.repositories import RepoChunksRepository
from app.repositories import RepositoryIntelligenceRepository
from app.repositories import SQLDatabaseInventoryRepository
from app.repositories import VectorSearchRepository
from app.repositories import DatabaseInventoryRepository
from app.services.audit_service import AuditService
from app.services.cloudrun_service import CloudRunService
from app.services.embedding_service import EmbeddingService
from app.services.metrics import AgentMetrics
from app.services.mongodb_service import MongoDBService
from app.services.observability_service import ObservabilityService
from app.services.postgres_document_service import PostgresDocumentService
from app.services.product_builder_service import ProductBuilderService
from app.services.refactor_service import RefactorService
from app.services.sql_database_service import SQLDatabaseService
from app.agents import WorkspaceAgent


LOGGER = logging.getLogger("yenkasa_code.orchestrator")


class YenkasaCodeOrchestrator:
    workspace_intent_keywords = (
        "read file",
        "open file",
        "create file",
        "write file",
        "delete file",
        "list directory",
        "list files",
    )

    database_intent_keywords = (
        "database",
        "mongo",
        "mongodb",
        "embedding",
        "embeddings",
        "repo_chunks",
        "memory_embeddings",
        "ai_embeddings",
        "yme_memories",
        "github_repositories",
        "storage",
        "collection",
        "collections",
        "list collections",
        "count documents",
        "document count",
        "show indexes",
        "list indexes",
        "missing indexes",
        "audit schema",
        "database schema",
        "schema inspection",
        "slow query",
        "slow queries",
        "database performance",
        "database health",
        "runtime exception",
        "runtime exceptions",
        "explain plan",
        "indexed file",
        "sql",
        "mysql",
        "postgres",
        "postgresql",
        "baleshop",
        "bale_shop",
        "yenkasa_store",
        "store database",
    )
    repository_intent_keywords = (
        "repository",
        "repo",
        "repos",
        "indexed repositories",
        "kotlin files",
        "python files",
        "repository size",
        "chunk count",
        "language breakdown",
    )
    vector_search_intent_keywords = (
        "check",
        "find",
        "search",
        "locate",
        "where is",
        "show code",
        "show implementation",
        "similar code",
        "heroku",
        "procfile",
        "dyno",
        "call server",
        "video call",
        "video server",
        "signaling",
        "signalling",
        "websocket",
        "socket.io",
        "socketio",
        "server",
    )
    audit_intent_keywords = (
        "audit",
        "review code",
        "security audit",
        "architecture audit",
        "analyze repository",
        "find issues",
    )
    refactor_intent_keywords = (
        "refactor",
        "improve architecture",
        "reduce technical debt",
        "clean up code",
        "extract service",
        "optimize structure",
    )
    cloudrun_intent_keywords = (
        "deployment",
        "cloud run",
        "revision",
        "service status",
        "traffic",
        "health",
        "healthy",
    )
    observability_intent_keywords = (
        "logs",
        "error",
        "errors",
        "failure",
        "failures",
        "failing",
        "performance",
        "incident",
        "monitoring",
    )
    product_builder_intent_keywords = (
        "generate",
        "build",
        "create project",
        "create api",
        "create schema",
        "create screen",
        "generate code",
    )

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        metrics: AgentMetrics | None = None,
        mongodb: MongoDBService | None = None,
        embedding_service: EmbeddingService | None = None,
        cloudrun_service: CloudRunService | None = None,
        observability_service: ObservabilityService | None = None,
        sql_database_service: SQLDatabaseService | None = None,
        repository_store: MongoDBService | PostgresDocumentService | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry()
        self.metrics = metrics or AgentMetrics()
        self.mongodb = mongodb
        self.repository_store = repository_store or mongodb
        self.embedding_service = embedding_service
        self.cloudrun_service = cloudrun_service
        self.observability_service = observability_service
        self.sql_database_service = sql_database_service
        self.reasoning = ReasoningEngine()
        self._register_foundation_agents()
        self.yio = YenkasaIntelligenceOrchestrator(registry=self.registry)

    def _register_foundation_agents(self) -> None:

        if (
                self.mongodb is not None
                and self.registry.get(WorkspaceAgent.name) is None
        ):
            self.registry.register(
                WorkspaceAgent(
                    workspace_root=self.mongodb.settings.workspace_root
                )
            )

        if self.registry.get(SystemAgent.name) is None:
            self.registry.register(SystemAgent())
        if self.mongodb is not None and self.registry.get(DatabaseAgent.name) is None:
            mongodb_settings = getattr(self.mongodb, "settings", None)
            self.registry.register(
                DatabaseAgent(
                    repo_chunks_repository=RepoChunksRepository(self.repository_store or self.mongodb),
                    memory_embeddings_repository=MemoryEmbeddingsRepository(self.mongodb),
                    database_inventory_repository=DatabaseInventoryRepository(self.mongodb, mongodb_settings)
                    if mongodb_settings is not None
                    else None,
                    sql_database_inventory_repository=SQLDatabaseInventoryRepository(
                        self.sql_database_service,
                        mongodb_settings,
                    )
                    if self.sql_database_service is not None and mongodb_settings is not None
                    else None,
                )
            )
        if self.repository_store is not None and self.registry.get(RepositoryAgent.name) is None:
            self.registry.register(
                RepositoryAgent(
                    repo_chunks_repository=RepoChunksRepository(self.repository_store),
                    repository_intelligence_repository=RepositoryIntelligenceRepository(self.repository_store),
                )
            )
        if self.mongodb is not None and self.embedding_service is not None and self.registry.get(VectorSearchAgent.name) is None:
            self.registry.register(
                VectorSearchAgent(
                    embedding_service=self.embedding_service,
                    vector_search_repository=VectorSearchRepository(self.repository_store or self.mongodb, memory_store=self.mongodb),
                )
            )
        if self.registry.get(CodeAuditAgent.name) is None:
            database_agent = self.registry.get(DatabaseAgent.name)
            repository_agent = self.registry.get(RepositoryAgent.name)
            vector_search_agent = self.registry.get(VectorSearchAgent.name)
            if database_agent is not None and repository_agent is not None and vector_search_agent is not None:
                self.registry.register(
                    CodeAuditAgent(
                        audit_service=AuditService(
                            database_agent=database_agent,
                            repository_agent=repository_agent,
                            vector_search_agent=vector_search_agent,
                        )
                    )
                )
        if self.registry.get(RefactorAgent.name) is None:
            code_audit_agent = self.registry.get(CodeAuditAgent.name)
            repository_agent = self.registry.get(RepositoryAgent.name)
            vector_search_agent = self.registry.get(VectorSearchAgent.name)
            if code_audit_agent is not None and repository_agent is not None and vector_search_agent is not None:
                self.registry.register(
                    RefactorAgent(
                        refactor_service=RefactorService(
                            code_audit_agent=code_audit_agent,
                            repository_agent=repository_agent,
                            vector_search_agent=vector_search_agent,
                        )
                    )
                )
        if self.cloudrun_service is not None and self.registry.get(CloudRunAgent.name) is None:
            self.registry.register(CloudRunAgent(cloudrun_service=self.cloudrun_service))
        if self.observability_service is not None and self.registry.get(ObservabilityAgent.name) is None:
            self.registry.register(ObservabilityAgent(observability_service=self.observability_service))
        if self.registry.get(ProductBuilderAgent.name) is None:
            self.registry.register(ProductBuilderAgent(product_builder_service=ProductBuilderService()))

    def discover_agents(self) -> list[AgentDescriptor]:
        return self.registry.list_agents()

    async def get_metrics(self) -> AgentMetricsResponse:
        return await self.metrics.snapshot(registered_agents=self.registry.names())

    async def route(self, request: AgentQueryRequest) -> AgentResponse:
        started = time.perf_counter()
        if request.agent is None:
            response = await self.yio.execute(query=request.query, context=request.context)
            duration_ms = int((time.perf_counter() - started) * 1000)
            await self.metrics.record(success=response.success)
            await self.metrics.record_yio_request(success=response.success, duration_ms=duration_ms)
            log_structured(
                LOGGER,
                logging.INFO if response.success else logging.ERROR,
                "yio_query_completed",
                selected_agent=response.agent,
                execution_time_ms=duration_ms,
                success=response.success,
                error=response.error,
            )
            return self.reasoning.finalize_response(query=request.query, response=response)

        agent_name = request.agent or self._select_agent(request.query)
        response: AgentResponse
        try:
            agent = self.registry.require(agent_name)
        except KeyError as exc:
            response = AgentResponse(agent=agent_name, success=False, result={}, error=str(exc))
            await self.metrics.record(success=False)
            log_structured(
                LOGGER,
                logging.WARNING,
                "agent_query_completed",
                selected_agent=agent_name,
                execution_time_ms=int((time.perf_counter() - started) * 1000),
                success=False,
                error=str(exc),
            )
            return self.reasoning.finalize_response(query=request.query, response=response)

        response = await agent.execute(query=request.query, context=request.context)
        duration_ms = int((time.perf_counter() - started) * 1000)
        await self.metrics.record(success=response.success)
        if agent.name == DatabaseAgent.name:
            await self.metrics.record_database_query(success=response.success, duration_ms=duration_ms)
        if agent.name == RepositoryAgent.name:
            await self.metrics.record_repository_query(success=response.success, duration_ms=duration_ms)
        if agent.name == VectorSearchAgent.name:
            await self.metrics.record_vector_query(success=response.success, duration_ms=duration_ms)
        if agent.name == CodeAuditAgent.name:
            await self.metrics.record_audit_query(success=response.success, duration_ms=duration_ms)
        if agent.name == RefactorAgent.name:
            await self.metrics.record_refactor_query(success=response.success, duration_ms=duration_ms)
        if agent.name == CloudRunAgent.name:
            await self.metrics.record_cloudrun_query(success=response.success, duration_ms=duration_ms)
        if agent.name == ObservabilityAgent.name:
            await self.metrics.record_observability_query(success=response.success, duration_ms=duration_ms)
        if agent.name == ProductBuilderAgent.name:
            await self.metrics.record_product_builder_query(success=response.success, duration_ms=duration_ms)
        log_structured(
            LOGGER,
            logging.INFO if response.success else logging.ERROR,
            "agent_query_completed",
            selected_agent=agent.name,
            execution_time_ms=duration_ms,
            success=response.success,
            error=response.error,
        )
        return self.reasoning.finalize_response(query=request.query, response=response)

    def _select_agent(self, query: str) -> str:
        normalized = query.lower()

        if self.registry.get(ProductBuilderAgent.name) is not None and any(
                keyword in normalized for keyword in self.product_builder_intent_keywords
        ):
            return ProductBuilderAgent.name

        if self.registry.get(ObservabilityAgent.name) is not None and any(
                keyword in normalized for keyword in self.observability_intent_keywords
        ):
            return ObservabilityAgent.name

        if self.registry.get(CloudRunAgent.name) is not None and any(
                keyword in normalized for keyword in self.cloudrun_intent_keywords
        ):
            return CloudRunAgent.name

        if self.registry.get(RefactorAgent.name) is not None and any(
                keyword in normalized for keyword in self.refactor_intent_keywords
        ):
            return RefactorAgent.name

        if self.registry.get(CodeAuditAgent.name) is not None and any(
                keyword in normalized for keyword in self.audit_intent_keywords
        ):
            return CodeAuditAgent.name

        if self.registry.get(VectorSearchAgent.name) is not None and any(
                keyword in normalized for keyword in self.vector_search_intent_keywords
        ):
            return VectorSearchAgent.name

        # WorkspaceAgent should be checked BEFORE RepositoryAgent
        if self.registry.get(WorkspaceAgent.name) is not None and any(
                keyword in normalized
                for keyword in self.workspace_intent_keywords
        ):
            return WorkspaceAgent.name

        if self.registry.get(RepositoryAgent.name) is not None and any(
                keyword in normalized for keyword in self.repository_intent_keywords
        ):
            return RepositoryAgent.name

        if self.registry.get(DatabaseAgent.name) is not None and any(
                keyword in normalized for keyword in self.database_intent_keywords
        ):
            return DatabaseAgent.name

        return SystemAgent.name
