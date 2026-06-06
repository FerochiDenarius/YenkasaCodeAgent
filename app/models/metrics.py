from __future__ import annotations

from pydantic import BaseModel


class AgentMetricsResponse(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    registered_agents: list[str]
