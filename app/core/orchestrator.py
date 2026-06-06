from __future__ import annotations

import logging
import time

from app.agents import AgentRegistry
from app.agents import DatabaseAgent
from app.agents import RepositoryAgent
from app.agents import SystemAgent
from app.agents import VectorSearchAgent
from app.core.logging import log_structured
from app.models.agent import AgentDescriptor
from app.models.agent import AgentQueryRequest
from app.models.agent import AgentResponse
from app.models.metrics import AgentMetricsResponse
from app.repositories import MemoryEmbeddingsRepository
from app.repositories import RepoChunksRepository
from app.repositories import RepositoryIntelligenceRepository
from app.repositories import VectorSearchRepository
from app.services.embedding_service import EmbeddingService
from app.services.metrics import AgentMetrics
from app.services.mongodb_service import MongoDBService


LOGGER = logging.getLogger("yenkasa_code.orchestrator")


class YenkasaCodeOrchestrator:
    database_intent_keywords = (
        "database",
        "mongo",
        "mongodb",
        "embedding",
        "embeddings",
        "repo_chunks",
        "memory_embeddings",
        "storage",
        "collection",
        "indexed file",
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
        "find",
        "search",
        "locate",
        "where is",
        "show code",
        "show implementation",
        "similar code",
    )

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        metrics: AgentMetrics | None = None,
        mongodb: MongoDBService | None = None,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry()
        self.metrics = metrics or AgentMetrics()
        self.mongodb = mongodb
        self.embedding_service = embedding_service
        self._register_foundation_agents()

    def _register_foundation_agents(self) -> None:
        if self.registry.get(SystemAgent.name) is None:
            self.registry.register(SystemAgent())
        if self.mongodb is not None and self.registry.get(DatabaseAgent.name) is None:
            self.registry.register(
                DatabaseAgent(
                    repo_chunks_repository=RepoChunksRepository(self.mongodb),
                    memory_embeddings_repository=MemoryEmbeddingsRepository(self.mongodb),
                )
            )
        if self.mongodb is not None and self.registry.get(RepositoryAgent.name) is None:
            self.registry.register(
                RepositoryAgent(
                    repo_chunks_repository=RepoChunksRepository(self.mongodb),
                    repository_intelligence_repository=RepositoryIntelligenceRepository(self.mongodb),
                )
            )
        if self.mongodb is not None and self.embedding_service is not None and self.registry.get(VectorSearchAgent.name) is None:
            self.registry.register(
                VectorSearchAgent(
                    embedding_service=self.embedding_service,
                    vector_search_repository=VectorSearchRepository(self.mongodb),
                )
            )

    def discover_agents(self) -> list[AgentDescriptor]:
        return self.registry.list_agents()

    async def get_metrics(self) -> AgentMetricsResponse:
        return await self.metrics.snapshot(registered_agents=self.registry.names())

    async def route(self, request: AgentQueryRequest) -> AgentResponse:
        started = time.perf_counter()
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
            return response

        response = await agent.execute(query=request.query, context=request.context)
        duration_ms = int((time.perf_counter() - started) * 1000)
        await self.metrics.record(success=response.success)
        if agent.name == DatabaseAgent.name:
            await self.metrics.record_database_query(success=response.success, duration_ms=duration_ms)
        if agent.name == RepositoryAgent.name:
            await self.metrics.record_repository_query(success=response.success, duration_ms=duration_ms)
        if agent.name == VectorSearchAgent.name:
            await self.metrics.record_vector_query(success=response.success, duration_ms=duration_ms)
        log_structured(
            LOGGER,
            logging.INFO if response.success else logging.ERROR,
            "agent_query_completed",
            selected_agent=agent.name,
            execution_time_ms=duration_ms,
            success=response.success,
            error=response.error,
        )
        return response

    def _select_agent(self, query: str) -> str:
        normalized = query.lower()
        if self.registry.get(VectorSearchAgent.name) is not None and any(
            keyword in normalized for keyword in self.vector_search_intent_keywords
        ):
            return VectorSearchAgent.name
        if self.registry.get(RepositoryAgent.name) is not None and any(
            keyword in normalized for keyword in self.repository_intent_keywords
        ):
            return RepositoryAgent.name
        if self.registry.get(DatabaseAgent.name) is not None and any(
            keyword in normalized for keyword in self.database_intent_keywords
        ):
            return DatabaseAgent.name
        return SystemAgent.name
