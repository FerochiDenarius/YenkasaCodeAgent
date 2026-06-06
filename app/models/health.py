from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    version: str
    registered_agents: int


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, dict[str, Any]]
