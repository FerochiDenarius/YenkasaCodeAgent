from __future__ import annotations

from typing import Any

from app.services.mongodb_service import MongoDBService


class RepoChunksRepository:
    collection_name = "ai_embeddings"

    def __init__(self, mongodb: MongoDBService) -> None:
        self.mongodb = mongodb

    async def count(self) -> int:
        return await self.mongodb.count_documents(self.collection_name)

    async def stats(self) -> dict[str, Any]:
        return await self.mongodb.collection_stats(self.collection_name)

    async def latest_indexed_file(self) -> dict[str, Any] | None:
        records = await self.mongodb.aggregate(
            self.collection_name,
            [
                {
                    "$addFields": {
                        "indexed_timestamp": {
                            "$ifNull": [
                                "$indexed_at",
                                {"$ifNull": ["$created_at", {"$ifNull": ["$updated_at", "$last_modified"]}]},
                            ]
                        }
                    }
                },
                {"$sort": {"indexed_timestamp": -1}},
                {"$limit": 1},
                {
                    "$project": {
                        "_id": 0,
                        "repo_name": 1,
                        "repository": 1,
                        "file_path": 1,
                        "path": 1,
                        "indexed_at": 1,
                        "created_at": 1,
                        "updated_at": 1,
                        "last_modified": 1,
                        "indexed_timestamp": 1,
                    }
                },
            ],
        )
        return records[0] if records else None

    async def top_repositories_by_chunk_count(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self.mongodb.aggregate(
            self.collection_name,
            [
                {
                    "$group": {
                        "_id": {"$ifNull": ["$repo_name", "$repository"]},
                        "chunk_count": {"$sum": 1},
                    }
                },
                {"$sort": {"chunk_count": -1}},
                {"$limit": limit},
                {"$project": {"_id": 0, "repository": "$_id", "chunk_count": 1}},
            ],
        )
