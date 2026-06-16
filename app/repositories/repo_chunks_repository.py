from __future__ import annotations

import re
from typing import Any


class RepoChunksRepository:
    collection_name = "ai_embeddings"

    def __init__(self, document_store) -> None:
        self.mongodb = document_store

    async def count(self) -> int:
        return await self.mongodb.count_documents(self.collection_name)

    async def stats(self) -> dict[str, Any]:
        return await self.mongodb.collection_stats(self.collection_name)

    async def latest_indexed_file(self) -> dict[str, Any] | None:
        if hasattr(self.mongodb, "latest_indexed_file"):
            return await self.mongodb.latest_indexed_file(self.collection_name)
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
        if hasattr(self.mongodb, "top_repositories_by_chunk_count"):
            return await self.mongodb.top_repositories_by_chunk_count(self.collection_name, limit=limit)
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

    async def search_text(self, query: str, *, limit: int = 5) -> list[dict[str, Any]]:
        if hasattr(self.mongodb, "search_repo_chunks_text"):
            return await self.mongodb.search_repo_chunks_text(query, self.collection_name, limit=limit)

        terms = self._search_terms(query)
        if not terms:
            return []
        regex = "|".join(re.escape(term) for term in terms)
        return await self.mongodb.aggregate(
            self.collection_name,
            [
                {
                    "$match": {
                        "$or": [
                            {"repo_name": {"$regex": regex, "$options": "i"}},
                            {"repository": {"$regex": regex, "$options": "i"}},
                            {"file_path": {"$regex": regex, "$options": "i"}},
                            {"path": {"$regex": regex, "$options": "i"}},
                            {"content": {"$regex": regex, "$options": "i"}},
                            {"text": {"$regex": regex, "$options": "i"}},
                            {"chunk": {"$regex": regex, "$options": "i"}},
                            {"snippet": {"$regex": regex, "$options": "i"}},
                        ]
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "repository": {"$ifNull": ["$repo_name", "$repository"]},
                        "file_path": {"$ifNull": ["$file_path", "$path"]},
                        "score": {"$literal": 1.0},
                        "snippet": {
                            "$substrCP": [
                                {
                                    "$ifNull": [
                                        "$content",
                                        {"$ifNull": ["$text", {"$ifNull": ["$chunk", "$snippet"]}]},
                                    ]
                                },
                                0,
                                500,
                            ]
                        },
                    }
                },
                {"$limit": max(1, int(limit))},
            ],
        )

    @staticmethod
    def _search_terms(query: str) -> list[str]:
        stopwords = {
            "about",
            "able",
            "aware",
            "check",
            "does",
            "file",
            "find",
            "handle",
            "handles",
            "hosting",
            "repo",
            "repository",
            "search",
            "show",
            "tell",
            "that",
            "this",
            "what",
            "where",
            "which",
            "with",
            "your",
        }
        terms = []
        for term in re.findall(r"[a-zA-Z0-9_.-]{3,}", query.lower()):
            if term in stopwords:
                continue
            if term not in terms:
                terms.append(term)
        return terms[:8]
