from __future__ import annotations

import logging
import time

from app.agents import AgentRegistry
from app.agents import SystemAgent
from app.core.logging import log_structured
from app.models.agent import AgentDescriptor
from app.models.agent import AgentQueryRequest
from app.models.agent import AgentResponse
from app.models.metrics import AgentMetricsResponse
from app.services.metrics import AgentMetrics


LOGGER = logging.getLogger("yenkasa_code.orchestrator")


class YenkasaCodeOrchestrator:
    def __init__(self, registry: AgentRegistry | None = None, metrics: AgentMetrics | None = None) -> None:
        self.registry = registry or AgentRegistry()
        self.metrics = metrics or AgentMetrics()
        self._register_foundation_agents()

    def _register_foundation_agents(self) -> None:
        if self.registry.get(SystemAgent.name) is None:
            self.registry.register(SystemAgent())

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
        await self.metrics.record(success=response.success)
        log_structured(
            LOGGER,
            logging.INFO if response.success else logging.ERROR,
            "agent_query_completed",
            selected_agent=agent.name,
            execution_time_ms=int((time.perf_counter() - started) * 1000),
            success=response.success,
            error=response.error,
        )
        return response

    def _select_agent(self, query: str) -> str:
        _ = query
        return SystemAgent.name
