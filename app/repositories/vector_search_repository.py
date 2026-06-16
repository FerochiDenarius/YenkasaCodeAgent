from __future__ import annotations

from typing import Any


class VectorSearchRepository:
    repo_chunks_collection = "ai_embeddings"
    memory_embeddings_collection = "yme_memories"
    repo_chunks_index = "repo_chunks_vector_index"
    memory_embeddings_index = "yme_memories_vector_index"

    def __init__(self, repo_store: Any, memory_store: Any | None = None) -> None:
        self.repo_store = repo_store
        self.memory_store = memory_store or repo_store

    @property
    def supports_repo_text_search(self) -> bool:
        return hasattr(self.repo_store, "search_repo_chunks_text")

    async def search_repo_chunks(
        self,
        query_vector: list[float],
        *,
        limit: int = 5,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        if query and hasattr(self.repo_store, "search_repo_chunks_text"):
            return await self.repo_store.search_repo_chunks_text(query, self.repo_chunks_collection, limit=limit)
        return await self._vector_search(
            store=self.repo_store,
            collection_name=self.repo_chunks_collection,
            index_name=self.repo_chunks_index,
            query_vector=query_vector,
            limit=limit,
            projection={
                "_id": 0,
                "file_path": {"$ifNull": ["$file_path", "$path"]},
                "repository": {"$ifNull": ["$repo_name", "$repository"]},
                "score": {"$meta": "vectorSearchScore"},
                "snippet": {"$substrCP": [{"$ifNull": ["$content", "$text"]}, 0, 500]},
            },
        )

    async def search_memories(self, query_vector: list[float], *, limit: int = 5) -> list[dict[str, Any]]:
        return await self._vector_search(
            store=self.memory_store,
            collection_name=self.memory_embeddings_collection,
            index_name=self.memory_embeddings_index,
            query_vector=query_vector,
            limit=limit,
            projection={
                "_id": 0,
                "file_path": {"$literal": None},
                "repository": {"$ifNull": ["$repo_name", "$repository"]},
                "score": {"$meta": "vectorSearchScore"},
                "snippet": {"$substrCP": [{"$ifNull": ["$content", "$text"]}, 0, 500]},
                "memory_id": 1,
            },
        )

    async def _vector_search(
        self,
        *,
        store: Any,
        collection_name: str,
        index_name: str,
        query_vector: list[float],
        limit: int,
        projection: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return await store.aggregate(
            collection_name,
            [
                {
                    "$vectorSearch": {
                        "index": index_name,
                        "path": "embedding",
                        "queryVector": query_vector,
                        "numCandidates": max(limit * 10, 50),
                        "limit": limit,
                    }
                },
                {"$project": projection},
            ],
        )
