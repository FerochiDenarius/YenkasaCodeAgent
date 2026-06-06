from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic import Field


class AgentQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    agent: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    agent: str
    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class AgentDescriptor(BaseModel):
    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
