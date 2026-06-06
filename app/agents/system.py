from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class SystemAgent(BaseAgent):
    name = "system"
    description = "Foundation agent for YenkasaCode orchestration and capability discovery."
    capabilities = [
        "agent_registration",
        "agent_discovery",
        "agent_routing",
        "health",
    ]

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        return {
            "message": "YenkasaCode Agent foundation is online.",
            "query": query,
            "context": context,
            "phase": "phase_1_foundation",
        }
