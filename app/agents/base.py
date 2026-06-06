from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any

from app.models.agent import AgentDescriptor
from app.models.agent import AgentResponse
from app.security.redaction import sanitize_error


class BaseAgent(ABC):
    name: str = "base"
    description: str = "Base YenkasaCode agent."
    capabilities: list[str] = []

    def descriptor(self) -> AgentDescriptor:
        return AgentDescriptor(
            name=self.name,
            description=self.description,
            capabilities=list(self.capabilities),
        )

    async def execute(self, query: str, context: dict[str, Any] | None = None) -> AgentResponse:
        try:
            result = await self.run(query=query, context=context or {})
            return AgentResponse(agent=self.name, success=True, result=result)
        except Exception as exc:
            return AgentResponse(agent=self.name, success=False, result={}, error=sanitize_error(exc))

    @abstractmethod
    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
