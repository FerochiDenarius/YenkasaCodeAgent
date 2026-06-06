from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.services.cloudrun_service import CloudRunService


class CloudRunAgent(BaseAgent):
    name = "CloudRunAgent"
    description = "Deployment intelligence agent for Cloud Run service status, revisions, traffic, and health."
    capabilities = [
        "service_status",
        "revision_status",
        "traffic_allocation",
        "deployment_history",
        "deployment_health",
    ]

    def __init__(self, cloudrun_service: CloudRunService) -> None:
        self.cloudrun_service = cloudrun_service

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        normalized = query.lower()
        if "history" in normalized:
            return {"deployment_history": await self.cloudrun_service.deployment_history()}
        if "revision" in normalized:
            return {"revision_status": await self.cloudrun_service.revision_status()}
        if "traffic" in normalized:
            return {"traffic_allocation": await self.cloudrun_service.traffic_allocation()}
        if "healthy" in normalized or "health" in normalized:
            return {"deployment_health": await self.cloudrun_service.deployment_health()}
        return {"service_status": await self.cloudrun_service.service_status()}
