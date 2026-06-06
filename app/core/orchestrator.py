from __future__ import annotations

import logging

from app.agents import AgentRegistry
from app.agents import SystemAgent
from app.models.agent import AgentDescriptor
from app.models.agent import AgentQueryRequest
from app.models.agent import AgentResponse


LOGGER = logging.getLogger("yenkasa_code.orchestrator")


class YenkasaCodeOrchestrator:
    def __init__(self, registry: AgentRegistry | None = None) -> None:
        self.registry = registry or AgentRegistry()
        self._register_foundation_agents()

    def _register_foundation_agents(self) -> None:
        if self.registry.get(SystemAgent.name) is None:
            self.registry.register(SystemAgent())

    def discover_agents(self) -> list[AgentDescriptor]:
        return self.registry.list_agents()

    async def route(self, request: AgentQueryRequest) -> AgentResponse:
        agent_name = request.agent or self._select_agent(request.query)
        try:
            agent = self.registry.require(agent_name)
        except KeyError as exc:
            LOGGER.warning("Agent routing failed agent=%s", agent_name)
            return AgentResponse(agent=agent_name, success=False, result={}, error=str(exc))

        LOGGER.info("Routing query to agent=%s", agent.name)
        return await agent.execute(query=request.query, context=request.context)

    def _select_agent(self, query: str) -> str:
        _ = query
        return SystemAgent.name
