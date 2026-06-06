from __future__ import annotations

from typing import Any

from app.services.mongodb_service import MongoDBService


class RepositoryIntelligenceRepository:
    collection_name = "repo_chunks"

    def __init__(self, mongodb: MongoDBService) -> None:
        self.mongodb = mongodb

    async def inventory(self) -> list[dict[str, Any]]:
        return await self.mongodb.aggregate(
            self.collection_name,
            [
                {
                    "$group": {
                        "_id": {"$ifNull": ["$repo_name", "$repository"]},
                        "chunk_count": {"$sum": 1},
                        "latest_indexed_at": {"$max": "$indexed_at"},
                        "files": {"$addToSet": {"$ifNull": ["$file_path", "$path"]}},
                    }
                },
                {"$sort": {"_id": 1}},
                {
                    "$project": {
                        "_id": 0,
                        "repository": "$_id",
                        "chunk_count": 1,
                        "file_count": {"$size": "$files"},
                        "latest_indexed_at": 1,
                    }
                },
            ],
        )

    async def language_breakdown(self) -> list[dict[str, Any]]:
        return await self.mongodb.aggregate(
            self.collection_name,
            [
                {
                    "$project": {
                        "language": {
                            "$toLower": {
                                "$ifNull": [
                                    "$language",
                                    {
                                        "$switch": {
                                            "branches": [
                                                {
                                                    "case": {
                                                        "$regexMatch": {
                                                            "input": {"$ifNull": ["$file_path", "$path"]},
                                                            "regex": "\\.kt$",
                                                            "options": "i",
                                                        }
                                                    },
                                                    "then": "kotlin",
                                                },
                                                {
                                                    "case": {
                                                        "$regexMatch": {
                                                            "input": {"$ifNull": ["$file_path", "$path"]},
                                                            "regex": "\\.py$",
                                                            "options": "i",
                                                        }
                                                    },
                                                    "then": "python",
                                                },
                                            ],
                                            "default": "unknown",
                                        }
                                    },
                                ]
                            }
                        },
                        "file_path": {"$ifNull": ["$file_path", "$path"]},
                    }
                },
                {
                    "$group": {
                        "_id": "$language",
                        "chunk_count": {"$sum": 1},
                        "files": {"$addToSet": "$file_path"},
                    }
                },
                {"$sort": {"chunk_count": -1}},
                {
                    "$project": {
                        "_id": 0,
                        "language": "$_id",
                        "chunk_count": 1,
                        "file_count": {"$size": "$files"},
                    }
                },
            ],
        )

    async def count_files_by_language(self, language: str) -> dict[str, Any]:
        extension = {"kotlin": "\\.kt$", "python": "\\.py$"}.get(language.lower())
        if extension is None:
            raise ValueError(f"Unsupported language '{language}'.")

        records = await self.mongodb.aggregate(
            self.collection_name,
            [
                {
                    "$match": {
                        "$or": [
                            {"language": {"$regex": f"^{language}$", "$options": "i"}},
                            {"file_path": {"$regex": extension, "$options": "i"}},
                            {"path": {"$regex": extension, "$options": "i"}},
                        ]
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "chunk_count": {"$sum": 1},
                        "files": {"$addToSet": {"$ifNull": ["$file_path", "$path"]}},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "language": language.lower(),
                        "chunk_count": 1,
                        "file_count": {"$size": "$files"},
                    }
                },
            ],
        )
        return records[0] if records else {"language": language.lower(), "chunk_count": 0, "file_count": 0}

    async def latest_activity(self) -> dict[str, Any] | None:
        records = await self.mongodb.aggregate(
            self.collection_name,
            [
                {"$sort": {"indexed_at": -1}},
                {"$limit": 1},
                {
                    "$project": {
                        "_id": 0,
                        "repository": {"$ifNull": ["$repo_name", "$repository"]},
                        "file_path": {"$ifNull": ["$file_path", "$path"]},
                        "indexed_at": 1,
                        "updated_at": 1,
                    }
                },
            ],
        )
        return records[0] if records else None

    async def health_anomalies(self) -> dict[str, Any]:
        missing_metadata = await self.mongodb.aggregate(
            self.collection_name,
            [
                {
                    "$match": {
                        "$or": [
                            {"repo_name": {"$exists": False}},
                            {"file_path": {"$exists": False}},
                            {"indexed_at": {"$exists": False}},
                        ]
                    }
                },
                {"$count": "count"},
            ],
        )
        return {
            "missing_metadata_count": missing_metadata[0]["count"] if missing_metadata else 0,
            "zero_chunk_repositories": [],
            "indexing_anomalies": [],
        }
