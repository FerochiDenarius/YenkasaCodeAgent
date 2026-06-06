from __future__ import annotations

import asyncio

from app.models.metrics import AgentMetricsResponse


class AgentMetrics:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

    async def record(self, *, success: bool) -> None:
        async with self._lock:
            self.total_requests += 1
            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1

    async def snapshot(self, *, registered_agents: list[str]) -> AgentMetricsResponse:
        async with self._lock:
            return AgentMetricsResponse(
                total_requests=self.total_requests,
                successful_requests=self.successful_requests,
                failed_requests=self.failed_requests,
                registered_agents=registered_agents,
            )
