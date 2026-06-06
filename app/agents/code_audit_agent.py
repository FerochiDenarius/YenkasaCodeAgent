from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.services.audit_service import AuditService


class CodeAuditAgent(BaseAgent):
    name = "CodeAuditAgent"
    description = "Engineering audit agent for repository, security, architecture, API, and code quality findings."
    capabilities = [
        "repository_audit",
        "security_audit",
        "architecture_audit",
        "api_audit",
        "code_quality_audit",
    ]

    def __init__(self, audit_service: AuditService) -> None:
        self.audit_service = audit_service

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        return {"findings": await self.audit_service.run_audit(query=query, context=context)}
