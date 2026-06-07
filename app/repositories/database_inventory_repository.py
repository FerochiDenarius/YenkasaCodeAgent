from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.config.settings import Settings
from app.services.mongodb_service import MongoDBService


class DatabaseInventoryRepository:
    def __init__(self, mongodb: MongoDBService, settings: Settings | None) -> None:
        self.mongodb = mongodb
        self.settings = settings

    def configured_databases(self) -> list[str]:
        if self.settings is None:
            return []
        seen: list[str] = []
        for database_name in (self.settings.mongodb_database, self.settings.mongodb_app_database):
            if database_name and database_name not in seen:
                seen.append(database_name)
        return seen

    async def inventory(self) -> dict[str, Any]:
        return {
            database_name: await self.database_inventory(database_name)
            for database_name in self.configured_databases()
        }

    async def list_collections(self, database_name: str | None = None) -> dict[str, Any]:
        if database_name:
            collections = await self.mongodb.list_collection_names(database_name=database_name)
            return {
                "database": database_name,
                "collections": sorted(collections),
                "evidence": self._evidence(
                    databases_scanned=1,
                    collections_scanned=len(collections),
                ),
            }
        databases = {}
        collection_count = 0
        for configured_database in self.configured_databases():
            collections = sorted(await self.mongodb.list_collection_names(database_name=configured_database))
            databases[configured_database] = collections
            collection_count += len(collections)
        return {
            "databases": databases,
            "collections": sorted({collection for values in databases.values() for collection in values}),
            "evidence": self._evidence(
                databases_scanned=len(databases),
                collections_scanned=collection_count,
            ),
        }

    async def collection_counts(self, database_name: str | None = None) -> dict[str, Any]:
        databases = [database_name] if database_name else self.configured_databases()
        counts: dict[str, dict[str, int]] = {}
        documents_analyzed = 0
        collections_scanned = 0
        for configured_database in databases:
            if not configured_database:
                continue
            counts[configured_database] = {}
            for collection_name in sorted(await self.mongodb.list_collection_names(database_name=configured_database)):
                count = await self.mongodb.count_documents(collection_name, database_name=configured_database)
                counts[configured_database][collection_name] = count
                documents_analyzed += count
                collections_scanned += 1
        return {
            "counts": counts,
            "evidence": self._evidence(
                databases_scanned=len(counts),
                collections_scanned=collections_scanned,
                documents_analyzed=documents_analyzed,
            ),
        }

    async def collection_indexes(
        self,
        *,
        collection_name: str | None = None,
        database_name: str | None = None,
    ) -> dict[str, Any]:
        databases = [database_name] if database_name else self.configured_databases()
        indexes: dict[str, dict[str, list[dict[str, Any]]]] = {}
        collections_scanned = 0
        indexes_inspected = 0
        for configured_database in databases:
            if not configured_database:
                continue
            collection_names = [collection_name] if collection_name else sorted(
                await self.mongodb.list_collection_names(database_name=configured_database)
            )
            indexes[configured_database] = {}
            for current_collection in collection_names:
                current_indexes = await self.mongodb.collection_indexes(
                    current_collection,
                    database_name=configured_database,
                )
                indexes[configured_database][current_collection] = [
                    self._normalize_index(index) for index in current_indexes
                ]
                collections_scanned += 1
                indexes_inspected += len(current_indexes)
        return {
            "indexes": indexes,
            "evidence": self._evidence(
                databases_scanned=len(indexes),
                collections_scanned=collections_scanned,
                indexes_inspected=indexes_inspected,
            ),
        }

    async def collections_missing_indexes(self, database_name: str | None = None) -> dict[str, Any]:
        databases = [database_name] if database_name else self.configured_databases()
        missing: list[dict[str, Any]] = []
        collections_scanned = 0
        indexes_inspected = 0
        documents_analyzed = 0
        for configured_database in databases:
            if not configured_database:
                continue
            for collection_name in sorted(await self.mongodb.list_collection_names(database_name=configured_database)):
                indexes = await self.mongodb.collection_indexes(collection_name, database_name=configured_database)
                count = await self.mongodb.count_documents(collection_name, database_name=configured_database)
                collections_scanned += 1
                indexes_inspected += len(indexes)
                documents_analyzed += count
                non_id_indexes = [
                    index for index in indexes
                    if list(dict(index.get("key", {})).keys()) != ["_id"]
                ]
                if count > 0 and not non_id_indexes:
                    missing.append(
                        {
                            "database": configured_database,
                            "collection": collection_name,
                            "document_count": count,
                            "index_count": len(indexes),
                            "issue": "Collection has documents but no secondary indexes.",
                            "recommendation": "Review query patterns and add targeted indexes for high-cardinality filters/sorts.",
                        }
                    )
        return {
            "collections_missing_indexes": missing,
            "evidence": self._evidence(
                databases_scanned=len([database for database in databases if database]),
                collections_scanned=collections_scanned,
                documents_analyzed=documents_analyzed,
                indexes_inspected=indexes_inspected,
            ),
        }

    async def schema_inspection(
        self,
        *,
        collection_name: str | None = None,
        database_name: str | None = None,
        sample_size: int = 25,
    ) -> dict[str, Any]:
        databases = [database_name] if database_name else self.configured_databases()
        schemas: dict[str, dict[str, Any]] = {}
        collections_scanned = 0
        documents_analyzed = 0
        for configured_database in databases:
            if not configured_database:
                continue
            collection_names = [collection_name] if collection_name else sorted(
                await self.mongodb.list_collection_names(database_name=configured_database)
            )
            schemas[configured_database] = {}
            for current_collection in collection_names:
                samples = await self.mongodb.sample_documents(
                    current_collection,
                    database_name=configured_database,
                    limit=sample_size,
                )
                schemas[configured_database][current_collection] = self._infer_schema(samples)
                collections_scanned += 1
                documents_analyzed += len(samples)
        return {
            "schemas": schemas,
            "evidence": self._evidence(
                databases_scanned=len(schemas),
                collections_scanned=collections_scanned,
                documents_analyzed=documents_analyzed,
            ),
        }

    async def explain(
        self,
        *,
        collection_name: str,
        filter_query: dict[str, Any] | None = None,
        database_name: str | None = None,
    ) -> dict[str, Any]:
        target_database = database_name or self._default_database()
        plan = await self.mongodb.explain_find(
            collection_name,
            filter_query=filter_query,
            database_name=target_database,
        )
        return {
            "database": target_database,
            "collection": collection_name,
            "filter": filter_query or {},
            "explain": plan,
            "evidence": self._evidence(databases_scanned=1, collections_scanned=1),
        }

    async def query_pattern_risks(self, *, query: str) -> dict[str, Any]:
        if self.settings is None:
            return {"query_pattern_risks": [], "evidence": self._evidence()}

        collection_names_set: set[str] = set()
        for database_name in self.configured_databases():
            for collection_name in await self.mongodb.list_collection_names(database_name=database_name):
                collection_names_set.add(collection_name)
        collection_names = sorted(collection_names_set)
        if not collection_names:
            return {"query_pattern_risks": [], "evidence": self._evidence()}

        patterns = []
        repo_collection = getattr(self.settings, "mongodb_chunks_collection", "ai_embeddings")
        for collection_name in collection_names:
            regex = collection_name.rstrip("s")
            try:
                matches = await self.mongodb.aggregate(
                    repo_collection,
                    [
                        {
                            "$match": {
                                "$or": [
                                    {"content": {"$regex": regex, "$options": "i"}},
                                    {"chunk_content": {"$regex": regex, "$options": "i"}},
                                    {"text": {"$regex": regex, "$options": "i"}},
                                    {"file_path": {"$regex": regex, "$options": "i"}},
                                ]
                            }
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "file_path": 1,
                                "repository": {"$ifNull": ["$repository", "$repo_name"]},
                                "function_name": {"$ifNull": ["$function_name", "$symbol"]},
                                "snippet": {
                                    "$substrCP": [
                                        {"$ifNull": ["$content", {"$ifNull": ["$chunk_content", "$text"]}]},
                                        0,
                                        240,
                                    ]
                                },
                            }
                        },
                        {"$limit": 3},
                    ],
                    database_name=self.settings.mongodb_database,
                )
            except Exception:
                matches = []
            for match in matches:
                patterns.append(
                    {
                        "file_path": match.get("file_path") or "unknown",
                        "function_name": match.get("function_name") or "unknown",
                        "collection": collection_name,
                        "likely_failure_point": self._likely_failure_point(query),
                        "confidence_score": 0.62 if match.get("file_path") else 0.42,
                        "repository": match.get("repository"),
                        "snippet": match.get("snippet"),
                    }
                )
        return {
            "query_pattern_risks": patterns[:12],
            "evidence": self._evidence(
                databases_scanned=len(self.configured_databases()),
                collections_scanned=len(collection_names),
                documents_analyzed=len(patterns),
            ),
        }

    async def database_inventory(self, database_name: str) -> dict[str, Any]:
        collections = await self.mongodb.list_collection_names(database_name=database_name)
        collection_summaries = []
        for collection_name in sorted(collections):
            summary: dict[str, Any] = {"collection": collection_name}
            try:
                summary["count"] = await self.mongodb.count_documents(
                    collection_name,
                    database_name=database_name,
                )
            except Exception as exc:
                summary["count_error"] = str(exc)
            try:
                stats = await self.mongodb.collection_stats(collection_name, database_name=database_name)
                summary["storage_size"] = stats.get("storageSize")
                summary["size"] = stats.get("size")
            except Exception as exc:
                summary["stats_error"] = str(exc)
            try:
                summary["index_count"] = len(
                    await self.mongodb.collection_indexes(collection_name, database_name=database_name)
                )
            except Exception as exc:
                summary["index_error"] = str(exc)
            collection_summaries.append(summary)
        return {
            "database": database_name,
            "collection_count": len(collections),
            "collections": collection_summaries,
        }

    def _default_database(self) -> str:
        if self.settings is None:
            return ""
        return self.settings.mongodb_database or self.settings.mongodb_app_database

    def _evidence(
        self,
        *,
        databases_scanned: int = 0,
        collections_scanned: int = 0,
        documents_analyzed: int = 0,
        indexes_inspected: int = 0,
    ) -> dict[str, Any]:
        return {
            "agent": "DatabaseAgent",
            "database_agent_executed": True,
            "databases_scanned": databases_scanned,
            "collections_scanned": collections_scanned,
            "documents_analyzed": documents_analyzed,
            "indexes_inspected": indexes_inspected,
        }

    def _normalize_index(self, index: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": index.get("name"),
            "key": dict(index.get("key", {})),
            "unique": bool(index.get("unique", False)),
            "sparse": bool(index.get("sparse", False)),
            "expire_after_seconds": index.get("expireAfterSeconds"),
        }

    def _infer_schema(self, samples: list[dict[str, Any]]) -> dict[str, Any]:
        field_types: dict[str, set[str]] = defaultdict(set)
        field_presence: dict[str, int] = defaultdict(int)
        sample_values: dict[str, Any] = {}
        for sample in samples:
            for field, value in sample.items():
                field_presence[field] += 1
                field_types[field].add(self._type_name(value))
                sample_values.setdefault(field, self._sample_value(value))

        total = len(samples)
        return {
            "sample_size": total,
            "fields": {
                field: {
                    "types": sorted(types),
                    "nullable": field_presence[field] < total or "null" in types,
                    "presence": field_presence[field],
                    "sample_value": sample_values.get(field),
                }
                for field, types in sorted(field_types.items())
            },
        }

    def _type_name(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "str"
        if isinstance(value, list):
            return "list"
        if isinstance(value, dict):
            return "object"
        return type(value).__name__

    def _sample_value(self, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, list):
            return [self._sample_value(item) for item in value[:3]]
        if isinstance(value, dict):
            return {key: self._sample_value(item) for key, item in list(value.items())[:5]}
        return str(value)

    def _likely_failure_point(self, query: str) -> str:
        normalized = query.lower()
        if "runtime exception" in normalized or "exception" in normalized:
            return "Potential runtime exception where code assumes database fields, indexes, or query results exist."
        if "slow" in normalized or "performance" in normalized:
            return "Potential slow query caused by missing secondary indexes or broad collection scans."
        return "Potential database usage mismatch between repository code and live collection metadata."
