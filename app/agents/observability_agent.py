from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.services.observability_service import ObservabilityService


class ObservabilityAgent(BaseAgent):
    name = "ObservabilityAgent"
    description = "Operational monitoring agent for logs, errors, performance, request trends, and incidents."
    capabilities = [
        "error_summaries",
        "log_summaries",
        "performance_metrics",
        "request_trends",
        "incident_detection",
    ]

    def __init__(self, observability_service: ObservabilityService) -> None:
        self.observability_service = observability_service

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        normalized = query.lower()
        hours = int(context.get("hours", 24))
        if "performance" in normalized:
            return {"performance_metrics": await self.observability_service.performance_metrics(query=query, hours=hours)}
        if "trend" in normalized:
            return {"request_trends": await self.observability_service.request_trends(query=query, hours=hours)}
        if "incident" in normalized:
            return {"incident_detection": await self.observability_service.incident_detection(query=query, hours=hours)}
        if ("logs" in normalized or " log " in f" {normalized} ") and "error" not in normalized and "failure" not in normalized:
            return {"log_summary": await self.observability_service.log_summary(query=query, hours=hours)}
        return {"error_summary": await self.observability_service.error_summary(query=query, hours=hours)}
