from __future__ import annotations

from typing import Any

from app.services.mongodb_service import MongoDBService


class MemoryEmbeddingsRepository:
    collection_name = "memory_embeddings"

    def __init__(self, mongodb: MongoDBService) -> None:
        self.mongodb = mongodb

    async def count(self) -> int:
        return await self.mongodb.count_documents(self.collection_name)

    async def stats(self) -> dict[str, Any]:
        return await self.mongodb.collection_stats(self.collection_name)

    async def latest_embedding(self) -> dict[str, Any] | None:
        records = await self.mongodb.aggregate(
            self.collection_name,
            [
                {
                    "$addFields": {
                        "embedding_timestamp": {
                            "$ifNull": ["$embedded_at", {"$ifNull": ["$created_at", "$updated_at"]}]
                        }
                    }
                },
                {"$sort": {"embedding_timestamp": -1}},
                {"$limit": 1},
                {
                    "$project": {
                        "_id": 0,
                        "memory_id": 1,
                        "repo_name": 1,
                        "created_at": 1,
                        "updated_at": 1,
                        "embedded_at": 1,
                        "embedding_timestamp": 1,
                    }
                },
            ],
        )
        return records[0] if records else None
