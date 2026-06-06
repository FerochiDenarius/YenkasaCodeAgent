from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.agent import AgentDescriptor


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        if not agent.name:
            raise ValueError("Agent name is required.")
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered.")
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def require(self, name: str) -> BaseAgent:
        agent = self.get(name)
        if agent is None:
            raise KeyError(f"Agent '{name}' is not registered.")
        return agent

    def list_agents(self) -> list[AgentDescriptor]:
        return [agent.descriptor() for agent in self._agents.values()]

    def names(self) -> list[str]:
        return list(self._agents.keys())
