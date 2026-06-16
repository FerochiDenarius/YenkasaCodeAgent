from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.repositories.vector_search_repository import VectorSearchRepository
from app.services.embedding_service import EmbeddingService


class VectorSearchAgent(BaseAgent):
    name = "VectorSearchAgent"
    description = "Semantic retrieval agent for indexed code chunks and memory embeddings."
    capabilities = [
        "semantic_code_search",
        "semantic_architecture_search",
        "memory_search",
    ]

    def __init__(self, embedding_service: EmbeddingService, vector_search_repository: VectorSearchRepository) -> None:
        self.embedding_service = embedding_service
        self.vector_search_repository = vector_search_repository

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        normalized = query.lower()
        limit = int(context.get("limit", 5))

        if "memory" in normalized or "memories" in normalized:
            query_vector = await self.embedding_service.embed_query(query)
            matches = await self.vector_search_repository.search_memories(query_vector, limit=limit)
        elif self.vector_search_repository.supports_repo_text_search:
            matches = await self.vector_search_repository.search_repo_chunks([], limit=limit, query=query)
        else:
            query_vector = await self.embedding_service.embed_query(query)
            matches = await self.vector_search_repository.search_repo_chunks(query_vector, limit=limit, query=query)

        return {"matches": [self._normalize_match(match) for match in matches]}

    def _normalize_match(self, match: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_path": match.get("file_path"),
            "repository": match.get("repository"),
            "similarity_score": match.get("score"),
            "snippet": match.get("snippet"),
        }
