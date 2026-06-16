from __future__ import annotations

import asyncio
import re
from typing import Any

from app.config.settings import Settings


class PostgresDocumentService:
    """Read-only adapter for YenkasaAI's PostgreSQL ai_documents store."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._pool: Any | None = None
        self._table = self._validated_identifier(settings.postgres_document_table)

    @property
    def configured(self) -> bool:
        return bool(self.settings.postgres_dsn or self._connection_parts_configured())

    @property
    def is_postgres_document_store(self) -> bool:
        return True

    @property
    def ai_embeddings_collection(self) -> str:
        return self.settings.postgres_ai_embeddings_collection or "ai_embeddings"

    async def readiness_check(self) -> bool:
        await self._fetchval("SELECT 1")
        await self._fetchval(f"SELECT count(*) FROM {self._table} WHERE collection=$1", self.ai_embeddings_collection)
        return True

    async def count_documents(
        self,
        collection_name: str,
        filter_query: dict[str, Any] | None = None,
        *,
        database_name: str | None = None,
    ) -> int:
        if filter_query:
            raise ValueError("PostgreSQL repository store only supports unfiltered count_documents.")
        return int(await self._fetchval(f"SELECT count(*) FROM {self._table} WHERE collection=$1", collection_name) or 0)

    async def collection_stats(self, collection_name: str, *, database_name: str | None = None) -> dict[str, Any]:
        count = await self.count_documents(collection_name)
        return {
            "ns": f"{self.settings.postgres_database or 'postgres'}.{self._table}.{collection_name}",
            "count": count,
            "size": None,
            "storageSize": None,
            "storage_backend": "postgres",
            "table": self._table,
            "collection": collection_name,
        }

    async def latest_indexed_file(self, collection_name: str | None = None) -> dict[str, Any] | None:
        rows = await self._fetch(
            f"""
            SELECT
                coalesce(document->>'repo_name', document->>'repository') AS repository,
                coalesce(document->>'repo_name', document->>'repository') AS repo_name,
                coalesce(document->>'file_path', document->>'path') AS file_path,
                coalesce(document->>'file_path', document->>'path') AS path,
                document->>'indexed_at' AS indexed_at,
                document->>'created_at' AS created_at,
                document->>'updated_at' AS updated_at,
                document->>'last_modified' AS last_modified,
                coalesce(
                    document->>'indexed_at',
                    document->>'created_at',
                    document->>'updated_at',
                    document->>'last_modified',
                    updated_at::text,
                    created_at::text
                ) AS indexed_timestamp
            FROM {self._table}
            WHERE collection=$1
            ORDER BY indexed_timestamp DESC NULLS LAST
            LIMIT 1
            """,
            collection_name or self.ai_embeddings_collection,
        )
        return dict(rows[0]) if rows else None

    async def top_repositories_by_chunk_count(
        self,
        collection_name: str | None = None,
        *,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        rows = await self._fetch(
            f"""
            SELECT
                coalesce(document->>'repo_name', document->>'repository') AS repository,
                count(*)::int AS chunk_count
            FROM {self._table}
            WHERE collection=$1
              AND nullif(coalesce(document->>'repo_name', document->>'repository'), '') IS NOT NULL
            GROUP BY repository
            ORDER BY chunk_count DESC, repository ASC
            LIMIT $2
            """,
            collection_name or self.ai_embeddings_collection,
            limit,
        )
        return [dict(row) for row in rows]

    async def repository_inventory(self, collection_name: str | None = None) -> list[dict[str, Any]]:
        rows = await self._fetch(
            f"""
            SELECT
                coalesce(document->>'repo_name', document->>'repository') AS repository,
                count(*)::int AS chunk_count,
                count(DISTINCT nullif(coalesce(document->>'file_path', document->>'path'), ''))::int AS file_count,
                max(coalesce(
                    document->>'indexed_at',
                    document->>'created_at',
                    document->>'updated_at',
                    document->>'last_modified',
                    updated_at::text,
                    created_at::text
                )) AS latest_indexed_at
            FROM {self._table}
            WHERE collection=$1
              AND nullif(coalesce(document->>'repo_name', document->>'repository'), '') IS NOT NULL
            GROUP BY repository
            ORDER BY repository ASC
            """,
            collection_name or self.ai_embeddings_collection,
        )
        return [dict(row) for row in rows]

    async def language_breakdown(self, collection_name: str | None = None) -> list[dict[str, Any]]:
        rows = await self._fetch(
            f"""
            WITH chunks AS (
                SELECT
                    coalesce(document->>'file_path', document->>'path') AS file_path,
                    lower(coalesce(
                        nullif(document->>'language', ''),
                        CASE
                            WHEN coalesce(document->>'file_path', document->>'path') ~* '\\.kt$' THEN 'kotlin'
                            WHEN coalesce(document->>'file_path', document->>'path') ~* '\\.py$' THEN 'python'
                            ELSE 'unknown'
                        END
                    )) AS language
                FROM {self._table}
                WHERE collection=$1
            )
            SELECT
                language,
                count(*)::int AS chunk_count,
                count(DISTINCT nullif(file_path, ''))::int AS file_count
            FROM chunks
            GROUP BY language
            ORDER BY chunk_count DESC, language ASC
            """,
            collection_name or self.ai_embeddings_collection,
        )
        return [dict(row) for row in rows]

    async def count_files_by_language(self, language: str, collection_name: str | None = None) -> dict[str, Any]:
        normalized = language.lower()
        extension = {"kotlin": r"\.kt$", "python": r"\.py$"}.get(normalized)
        if extension is None:
            raise ValueError(f"Unsupported language '{language}'.")

        rows = await self._fetch(
            f"""
            SELECT
                $2::text AS language,
                count(*)::int AS chunk_count,
                count(DISTINCT nullif(coalesce(document->>'file_path', document->>'path'), ''))::int AS file_count
            FROM {self._table}
            WHERE collection=$1
              AND (
                  lower(document->>'language') = $2
                  OR coalesce(document->>'file_path', document->>'path') ~* $3
              )
            """,
            collection_name or self.ai_embeddings_collection,
            normalized,
            extension,
        )
        return dict(rows[0]) if rows else {"language": normalized, "chunk_count": 0, "file_count": 0}

    async def health_anomalies(self, collection_name: str | None = None) -> dict[str, Any]:
        missing_metadata_count = await self._fetchval(
            f"""
            SELECT count(*)::int
            FROM {self._table}
            WHERE collection=$1
              AND (
                  nullif(coalesce(document->>'repo_name', document->>'repository'), '') IS NULL
                  OR nullif(coalesce(document->>'file_path', document->>'path'), '') IS NULL
                  OR coalesce(
                      document->>'indexed_at',
                      document->>'created_at',
                      document->>'updated_at',
                      document->>'last_modified'
                  ) IS NULL
              )
            """,
            collection_name or self.ai_embeddings_collection,
        )
        return {
            "missing_metadata_count": int(missing_metadata_count or 0),
            "zero_chunk_repositories": [],
            "indexing_anomalies": [],
        }

    async def search_repo_chunks_text(
        self,
        query: str,
        collection_name: str | None = None,
        *,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        terms = self._repo_search_terms(query)
        if not terms:
            return []
        patterns = [f"%{term}%" for term in terms]
        rows = await self._fetch(
            f"""
            WITH chunks AS (
                SELECT
                    coalesce(document->>'repo_name', document->>'repository') AS repository,
                    coalesce(document->>'file_path', document->>'path') AS file_path,
                    coalesce(
                        document->>'content',
                        document->>'text',
                        document->>'chunk',
                        document->>'snippet',
                        document->>'page_content',
                        ''
                    ) AS content
                FROM {self._table}
                WHERE collection=$1
            )
            SELECT
                repository,
                file_path,
                (
                    CASE WHEN lower(coalesce(file_path, '')) LIKE ANY($2::text[]) THEN 4 ELSE 0 END +
                    CASE WHEN lower(coalesce(repository, '')) LIKE ANY($2::text[]) THEN 2 ELSE 0 END +
                    CASE WHEN lower(content) LIKE ANY($2::text[]) THEN 1 ELSE 0 END
                )::float AS score,
                substring(content from 1 for 500) AS snippet
            FROM chunks
            WHERE nullif(coalesce(repository, ''), '') IS NOT NULL
              AND (
                  lower(coalesce(file_path, '')) LIKE ANY($2::text[])
                  OR lower(coalesce(repository, '')) LIKE ANY($2::text[])
                  OR lower(content) LIKE ANY($2::text[])
              )
            ORDER BY score DESC, repository ASC, file_path ASC
            LIMIT $3
            """,
            collection_name or self.ai_embeddings_collection,
            patterns,
            max(1, int(limit)),
        )
        return [dict(row) for row in rows]

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _fetch(self, query: str, *args: Any) -> list[Any]:
        pool = await self._get_pool()
        return await asyncio.wait_for(
            pool.fetch(query, *args),
            timeout=self.settings.external_timeout_seconds,
        )

    async def _fetchval(self, query: str, *args: Any) -> Any:
        pool = await self._get_pool()
        return await asyncio.wait_for(
            pool.fetchval(query, *args),
            timeout=self.settings.external_timeout_seconds,
        )

    async def _get_pool(self) -> Any:
        if self._pool is None:
            if not self.configured:
                raise RuntimeError("PostgreSQL repository store is not configured.")
            try:
                import asyncpg
            except ImportError as exc:
                raise RuntimeError("asyncpg is required for PostgreSQL repository access.") from exc
            self._pool = await asyncpg.create_pool(**self._pool_kwargs())
        return self._pool

    def _pool_kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "min_size": max(1, int(self.settings.postgres_pool_min_size)),
            "max_size": max(1, int(self.settings.postgres_pool_max_size)),
            "command_timeout": max(1, int(self.settings.postgres_command_timeout_s)),
        }
        if self.settings.postgres_dsn:
            kwargs["dsn"] = self.settings.postgres_dsn
            return kwargs
        kwargs.update(
            user=self.settings.postgres_user,
            password=self.settings.postgres_password,
            database=self.settings.postgres_database,
            host=self._postgres_host(),
            port=self.settings.postgres_port,
        )
        return kwargs

    def _postgres_host(self) -> str:
        if self.settings.postgres_host:
            return self.settings.postgres_host
        if self.settings.postgres_cloud_sql_connection_name:
            return f"/cloudsql/{self.settings.postgres_cloud_sql_connection_name}"
        return "127.0.0.1"

    def _connection_parts_configured(self) -> bool:
        return bool(
            self.settings.postgres_user
            and self.settings.postgres_password
            and self.settings.postgres_database
        )

    @staticmethod
    def _validated_identifier(identifier: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", identifier):
            raise ValueError("PostgreSQL document table must be a simple SQL identifier.")
        return identifier

    @staticmethod
    def _repo_search_terms(query: str) -> list[str]:
        normalized = query.lower()
        terms = {
            token
            for token in re.findall(r"[a-z0-9_.-]{3,}", normalized)
            if token not in {"repo", "repos", "repository", "repositories", "check", "find", "search", "show", "have", "aware"}
        }
        if any(token in normalized for token in ("heroku", "dyno", "procfile")):
            terms.update({"heroku", "procfile", "dyno", "app.json"})
        if any(token in normalized for token in ("call", "video", "signaling", "signalling", "websocket", "socket.io", "socketio")):
            terms.update({"call", "video", "server", "socket", "socket.io", "websocket", "signaling", "signalling", "rtc", "agora"})
        return sorted(terms)[:20]
