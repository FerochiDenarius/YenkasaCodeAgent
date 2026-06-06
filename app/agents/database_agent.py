from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.repositories.memory_embeddings_repository import MemoryEmbeddingsRepository
from app.repositories.repo_chunks_repository import RepoChunksRepository


class DatabaseAgent(BaseAgent):
    name = "DatabaseAgent"
    description = "Read-only operational agent for MongoDB collection counts, stats, and latest records."
    capabilities = [
        "repo_chunks_count",
        "memory_embeddings_count",
        "collection_storage_stats",
        "latest_indexed_file",
        "latest_embedding_timestamp",
        "top_repositories_by_chunk_count",
    ]

    def __init__(
        self,
        repo_chunks_repository: RepoChunksRepository,
        memory_embeddings_repository: MemoryEmbeddingsRepository,
    ) -> None:
        self.repo_chunks_repository = repo_chunks_repository
        self.memory_embeddings_repository = memory_embeddings_repository

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        normalized = query.lower()

        if "top" in normalized and "repo" in normalized and "chunk" in normalized:
            limit = int(context.get("limit", 10))
            return {"top_repositories": await self.repo_chunks_repository.top_repositories_by_chunk_count(limit=limit)}

        if "latest" in normalized and ("indexed file" in normalized or "file" in normalized):
            return {"latest_indexed_file": await self.repo_chunks_repository.latest_indexed_file()}

        if "latest" in normalized and ("embedding" in normalized or "timestamp" in normalized):
            return {"latest_embedding": await self.memory_embeddings_repository.latest_embedding()}

        if "storage" in normalized or "stats" in normalized or "size" in normalized:
            if "memory_embeddings" in normalized or "embedding" in normalized:
                return {"collection": "memory_embeddings", "stats": await self.memory_embeddings_repository.stats()}
            if "repo_chunks" in normalized or "chunk" in normalized:
                return {"collection": "repo_chunks", "stats": await self.repo_chunks_repository.stats()}
            return {
                "collections": {
                    "repo_chunks": await self.repo_chunks_repository.stats(),
                    "memory_embeddings": await self.memory_embeddings_repository.stats(),
                }
            }

        if "memory_embeddings" in normalized or "embedding" in normalized:
            return {"collection": "memory_embeddings", "count": await self.memory_embeddings_repository.count()}

        if "repo_chunks" in normalized or "chunk" in normalized:
            return {"collection": "repo_chunks", "count": await self.repo_chunks_repository.count()}

        return {
            "repo_chunks_count": await self.repo_chunks_repository.count(),
            "memory_embeddings_count": await self.memory_embeddings_repository.count(),
        }
