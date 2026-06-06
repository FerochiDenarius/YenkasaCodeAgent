from __future__ import annotations

from typing import Any

from app.services.mongodb_service import MongoDBService


class VectorSearchRepository:
    repo_chunks_collection = "repo_chunks"
    memory_embeddings_collection = "memory_embeddings"
    repo_chunks_index = "repo_chunks_vector_index"
    memory_embeddings_index = "memory_embeddings_vector_index"

    def __init__(self, mongodb: MongoDBService) -> None:
        self.mongodb = mongodb

    async def search_repo_chunks(self, query_vector: list[float], *, limit: int = 5) -> list[dict[str, Any]]:
        return await self._vector_search(
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
        collection_name: str,
        index_name: str,
        query_vector: list[float],
        limit: int,
        projection: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return await self.mongodb.aggregate(
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
