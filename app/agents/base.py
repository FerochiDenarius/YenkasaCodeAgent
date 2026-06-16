from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import Any

from app.models.agent import AgentDescriptor
from app.models.agent import AgentResponse
from app.security.redaction import sanitize_error
from app.utils.evidence_package import build_evidence_package


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
            return AgentResponse(
                agent=self.name,
                success=True,
                result=result,
                evidence_package=build_evidence_package(agent=self.name, result=result, success=True, query=query),
            )
        except Exception as exc:
            error = sanitize_error(exc)
            return AgentResponse(
                agent=self.name,
                success=False,
                result={},
                error=error,
                evidence_package=build_evidence_package(agent=self.name, result={}, success=False, error=error, query=query),
            )

    @abstractmethod
    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
