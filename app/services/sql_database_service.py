from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import unquote
from urllib.parse import urlparse

from app.config.settings import Settings


class SQLDatabaseService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._connection: Any | None = None

    @property
    def configured(self) -> bool:
        return bool(self.settings.baleshop_database_url)

    @property
    def database_name(self) -> str:
        parsed_name = self._parse_url().get("database") if self.configured else ""
        return parsed_name or self.settings.baleshop_database_name

    def _parse_url(self) -> dict[str, Any]:
        parsed = urlparse(self.settings.baleshop_database_url)
        if parsed.scheme not in {"mysql", "mysql+pymysql"}:
            raise RuntimeError("BALESHOP_DATABASE_URL must use mysql:// or mysql+pymysql://.")
        database = parsed.path.lstrip("/")
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": unquote(database),
        }

    def _get_connection(self) -> Any:
        if not self.configured:
            raise RuntimeError("BALESHOP_DATABASE_URL is not configured.")
        if self._connection is None:
            try:
                import pymysql
                from pymysql.cursors import DictCursor
            except ImportError as exc:
                raise RuntimeError("pymysql is required for SQL database access.") from exc
            config = self._parse_url()
            self._connection = pymysql.connect(
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
                database=config["database"] or self.settings.baleshop_database_name,
                connect_timeout=int(self.settings.external_timeout_seconds),
                read_timeout=int(self.settings.external_timeout_seconds),
                write_timeout=int(self.settings.external_timeout_seconds),
                cursorclass=DictCursor,
                autocommit=True,
            )
        return self._connection

    async def ping(self) -> bool:
        await self._run_query("SELECT 1 AS ok")
        return True

    async def readiness_check(self) -> bool:
        if not self.configured:
            return True
        return await self.ping()

    async def list_tables(self) -> list[str]:
        rows = await self._run_query(
            """
            SELECT TABLE_NAME AS table_name
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
            ORDER BY TABLE_NAME
            """,
            (self.database_name,),
        )
        return [row["table_name"] for row in rows]

    async def table_count(self, table_name: str) -> int:
        rows = await self._run_query(f"SELECT COUNT(*) AS count FROM {self._quote_identifier(table_name)}")
        return int(rows[0]["count"]) if rows else 0

    async def table_sample(self, table_name: str) -> dict[str, Any] | None:
        rows = await self._run_query(f"SELECT * FROM {self._quote_identifier(table_name)} LIMIT 1")
        return rows[0] if rows else None

    async def table_indexes(self, table_name: str) -> list[dict[str, Any]]:
        return await self._run_query(f"SHOW INDEX FROM {self._quote_identifier(table_name)}")

    async def table_storage(self, table_name: str) -> dict[str, Any]:
        rows = await self._run_query(
            """
            SELECT DATA_LENGTH AS data_size, INDEX_LENGTH AS index_size, DATA_FREE AS data_free
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """,
            (self.database_name, table_name),
        )
        return rows[0] if rows else {"data_size": None, "index_size": None, "data_free": None}

    async def close(self) -> None:
        if self._connection is not None:
            connection = self._connection
            self._connection = None
            await asyncio.to_thread(connection.close)

    async def _run_query(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        def execute() -> list[dict[str, Any]]:
            connection = self._get_connection()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(query, params)
                    return list(cursor.fetchall())
            except Exception:
                self._reset_connection()
                raise

        return await asyncio.wait_for(
            asyncio.to_thread(execute),
            timeout=self.settings.external_timeout_seconds,
        )

    def _reset_connection(self) -> None:
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return f"`{identifier.replace('`', '``')}`"
