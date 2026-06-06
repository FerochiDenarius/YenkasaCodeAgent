from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.services.product_builder_service import ProductBuilderService


class ProductBuilderAgent(BaseAgent):
    name = "ProductBuilderAgent"
    description = "Generate-only agent for proposed app, API, database, and documentation artifacts."
    capabilities = [
        "flutter_generation",
        "fastapi_generation",
        "nodejs_generation",
        "database_schema_generation",
        "documentation_generation",
    ]

    def __init__(self, product_builder_service: ProductBuilderService) -> None:
        self.product_builder_service = product_builder_service

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        return self.product_builder_service.generate(query=query, context=context)
