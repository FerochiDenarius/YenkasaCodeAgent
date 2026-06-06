from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.services.refactor_service import RefactorService


class RefactorAgent(BaseAgent):
    name = "RefactorAgent"
    description = "Planning-only agent for refactor recommendations, migration plans, and technical debt reports."
    capabilities = [
        "technical_debt_analysis",
        "service_extraction_analysis",
        "duplication_analysis",
        "dependency_analysis",
        "architecture_refactor_analysis",
    ]

    def __init__(self, refactor_service: RefactorService) -> None:
        self.refactor_service = refactor_service

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        return {"recommendations": await self.refactor_service.generate_plan(query=query, context=context)}
