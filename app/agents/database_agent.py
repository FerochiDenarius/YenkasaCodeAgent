from __future__ import annotations

import re
from typing import Any

from app.agents.base import BaseAgent
from app.repositories.database_inventory_repository import DatabaseInventoryRepository
from app.repositories.memory_embeddings_repository import MemoryEmbeddingsRepository
from app.repositories.repo_chunks_repository import RepoChunksRepository
from app.repositories.sql_database_inventory_repository import SQLDatabaseInventoryRepository


class DatabaseAgent(BaseAgent):
    name = "DatabaseAgent"
    description = "Read-only operational agent for MongoDB collection counts, stats, and latest records."
    capabilities = [
        "repo_chunks_count",
        "memory_embeddings_count",
        "list_collections",
        "collection_counts",
        "collection_storage_stats",
        "index_inspection",
        "missing_index_detection",
        "schema_inspection",
        "explain_plan",
        "query_pattern_risk_analysis",
        "database_health",
        "latest_indexed_file",
        "latest_embedding_timestamp",
        "top_repositories_by_chunk_count",
        "multi_database_inventory",
        "sql_database_inventory",
    ]

    def __init__(
        self,
        repo_chunks_repository: RepoChunksRepository,
        memory_embeddings_repository: MemoryEmbeddingsRepository,
        database_inventory_repository: DatabaseInventoryRepository | None = None,
        sql_database_inventory_repository: SQLDatabaseInventoryRepository | None = None,
    ) -> None:
        self.repo_chunks_repository = repo_chunks_repository
        self.memory_embeddings_repository = memory_embeddings_repository
        self.database_inventory_repository = database_inventory_repository
        self.sql_database_inventory_repository = sql_database_inventory_repository

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        normalized = query.lower()
        database_name = self._database_name(normalized, context)
        collection_name = self._collection_name(query, context)

        if self.sql_database_inventory_repository is not None and (
            "baleshop" in normalized
            or "bale_shop" in normalized
            or "yenkasa_store" in normalized
            or "sql" in normalized
            or "mysql" in normalized
            or "store database" in normalized
        ):
            return {
                "sql_database_inventory": await self.sql_database_inventory_repository.inventory()
            }

        if self.database_inventory_repository is not None and (
            "list all collections" in normalized
            or "list every mongodb collection" in normalized
            or "list collections" in normalized
            or "show collections" in normalized
            or "collection inventory" in normalized
            or "database inventory" in normalized
            or "both databases" in normalized
            or "all databases" in normalized
            or "yenkasachat" in normalized
            or "yenkasa_ai_db" in normalized
        ):
            if "yenkasachat" in normalized:
                return {
                    "database_inventory": await self.database_inventory_repository.database_inventory(
                        self.database_inventory_repository.settings.mongodb_app_database
                    ),
                    "evidence": self._evidence(databases_scanned=1),
                }
            if "yenkasa_ai_db" in normalized:
                return {
                    "database_inventory": await self.database_inventory_repository.database_inventory(
                        self.database_inventory_repository.settings.mongodb_database
                    ),
                    "evidence": self._evidence(databases_scanned=1),
                }
            if "list" in normalized or "show collections" in normalized:
                return await self.database_inventory_repository.list_collections(database_name=database_name)
            result = {"databases": await self.database_inventory_repository.inventory()}
            if self.sql_database_inventory_repository is not None:
                result["sql_databases"] = {
                    "baleshop": await self.sql_database_inventory_repository.inventory()
                }
            result["evidence"] = self._evidence(databases_scanned=len(self.database_inventory_repository.configured_databases()))
            return result

        if self.database_inventory_repository is not None and (
            "count documents" in normalized
            or "document count" in normalized
            or "documents exist" in normalized
            or "how many documents" in normalized
        ):
            return await self.database_inventory_repository.collection_counts(database_name=database_name)

        if self.database_inventory_repository is not None and (
            "show indexes" in normalized
            or "list indexes" in normalized
            or "get indexes" in normalized
            or "index definitions" in normalized
        ):
            return await self.database_inventory_repository.collection_indexes(
                collection_name=collection_name,
                database_name=database_name,
            )

        if self.database_inventory_repository is not None and (
            "missing indexes" in normalized
            or "missing index" in normalized
            or "find collections missing indexes" in normalized
        ):
            return await self.database_inventory_repository.collections_missing_indexes(database_name=database_name)

        if self.database_inventory_repository is not None and (
            "audit schema" in normalized
            or "database schema" in normalized
            or "schema discovery" in normalized
            or "schema inspection" in normalized
            or "infer schema" in normalized
        ):
            schema = await self.database_inventory_repository.schema_inspection(
                collection_name=collection_name,
                database_name=database_name,
                sample_size=int(context.get("sample_size", 25)),
            )
            missing_indexes = await self.database_inventory_repository.collections_missing_indexes(database_name=database_name)
            return {
                "schema_inspection": schema,
                "index_findings": missing_indexes,
                "evidence": self._combine_evidence(schema.get("evidence", {}), missing_indexes.get("evidence", {})),
            }

        if self.database_inventory_repository is not None and (
            "explain" in normalized
            or "explain plan" in normalized
        ):
            if not collection_name:
                return {
                    "error": "A collection name is required for explain plan inspection.",
                    "evidence": self._evidence(database_agent_executed=True),
                }
            return await self.database_inventory_repository.explain(
                collection_name=collection_name,
                filter_query=context.get("filter") if isinstance(context.get("filter"), dict) else {},
                database_name=database_name,
            )

        if self.database_inventory_repository is not None and (
            "slow query" in normalized
            or "slow queries" in normalized
            or "database performance" in normalized
            or "runtime exception" in normalized
            or "runtime exceptions" in normalized
            or "exception hotspot" in normalized
            or "database health" in normalized
        ):
            missing_indexes = await self.database_inventory_repository.collections_missing_indexes(database_name=database_name)
            query_risks = await self.database_inventory_repository.query_pattern_risks(query=query)
            return {
                "database_health": {
                    "missing_indexes": missing_indexes.get("collections_missing_indexes", []),
                    "query_pattern_risks": query_risks.get("query_pattern_risks", []),
                },
                "evidence": self._combine_evidence(missing_indexes.get("evidence", {}), query_risks.get("evidence", {})),
            }

        if "top" in normalized and "repo" in normalized and "chunk" in normalized:
            limit = int(context.get("limit", 10))
            return {
                "top_repositories": await self.repo_chunks_repository.top_repositories_by_chunk_count(limit=limit),
                "evidence": self._evidence(collections_scanned=1),
            }

        if "latest" in normalized and ("indexed file" in normalized or "file" in normalized):
            return {
                "latest_indexed_file": await self.repo_chunks_repository.latest_indexed_file(),
                "evidence": self._evidence(collections_scanned=1),
            }

        if "latest" in normalized and ("embedding" in normalized or "timestamp" in normalized):
            return {
                "latest_embedding": await self.memory_embeddings_repository.latest_embedding(),
                "evidence": self._evidence(collections_scanned=1),
            }

        if "storage" in normalized or "stats" in normalized or "size" in normalized:
            if "memory_embeddings" in normalized or "embedding" in normalized:
                return {
                    "collection": self.memory_embeddings_repository.collection_name,
                    "alias": "memory_embeddings",
                    "stats": await self.memory_embeddings_repository.stats(),
                    "evidence": self._evidence(collections_scanned=1),
                }
            if "repo_chunks" in normalized or "chunk" in normalized:
                return {
                    "collection": self.repo_chunks_repository.collection_name,
                    "alias": "repo_chunks",
                    "stats": await self.repo_chunks_repository.stats(),
                    "evidence": self._evidence(collections_scanned=1),
                }
            return {
                "collections": {
                    self.repo_chunks_repository.collection_name: await self.repo_chunks_repository.stats(),
                    self.memory_embeddings_repository.collection_name: await self.memory_embeddings_repository.stats(),
                },
                "evidence": self._evidence(collections_scanned=2),
            }

        if "memory_embeddings" in normalized or "embedding" in normalized:
            return {
                "collection": self.memory_embeddings_repository.collection_name,
                "alias": "memory_embeddings",
                "count": await self.memory_embeddings_repository.count(),
                "evidence": self._evidence(collections_scanned=1),
            }

        if "repo_chunks" in normalized or "chunk" in normalized:
            return {
                "collection": self.repo_chunks_repository.collection_name,
                "alias": "repo_chunks",
                "count": await self.repo_chunks_repository.count(),
                "evidence": self._evidence(collections_scanned=1),
            }

        return {
            "repo_chunks_count": await self.repo_chunks_repository.count(),
            "memory_embeddings_count": await self.memory_embeddings_repository.count(),
            "repo_chunks_collection": self.repo_chunks_repository.collection_name,
            "memory_embeddings_collection": self.memory_embeddings_repository.collection_name,
            "evidence": self._evidence(collections_scanned=2),
        }

    def _database_name(self, normalized_query: str, context: dict[str, Any]) -> str | None:
        context_database = context.get("database") or context.get("database_name")
        if isinstance(context_database, str) and context_database.strip():
            return context_database.strip()
        if self.database_inventory_repository is None or self.database_inventory_repository.settings is None:
            return None
        if "yenkasachat" in normalized_query or "yenkasa chat" in normalized_query:
            return self.database_inventory_repository.settings.mongodb_app_database
        if "yenkasa_ai_db" in normalized_query or "yenkasa ai" in normalized_query:
            return self.database_inventory_repository.settings.mongodb_database
        return None

    def _collection_name(self, query: str, context: dict[str, Any]) -> str | None:
        context_collection = context.get("collection") or context.get("collection_name")
        if isinstance(context_collection, str) and context_collection.strip():
            return context_collection.strip()
        normalized = query.lower()
        match = re.search(r"\b(?:for|in|on|from)\s+([a-zA-Z_][\w.-]*)\s+collection\b", normalized)
        if match:
            return match.group(1)
        match = re.search(r"\b([a-zA-Z_][\w.-]*)\s+collection\b", normalized)
        if match and match.group(1) not in {"every", "each", "all", "mongodb", "mongo"}:
            return match.group(1)
        return None

    def _evidence(
        self,
        *,
        database_agent_executed: bool = True,
        databases_scanned: int = 0,
        collections_scanned: int = 0,
        documents_analyzed: int = 0,
        indexes_inspected: int = 0,
    ) -> dict[str, Any]:
        return {
            "agent": self.name,
            "database_agent_executed": database_agent_executed,
            "databases_scanned": databases_scanned,
            "collections_scanned": collections_scanned,
            "documents_analyzed": documents_analyzed,
            "indexes_inspected": indexes_inspected,
        }

    def _combine_evidence(self, *items: dict[str, Any]) -> dict[str, Any]:
        combined = self._evidence()
        for item in items:
            for key in ("databases_scanned", "collections_scanned", "documents_analyzed", "indexes_inspected"):
                combined[key] += int(item.get(key, 0) or 0)
        return combined
