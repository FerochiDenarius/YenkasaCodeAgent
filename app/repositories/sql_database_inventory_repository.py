from __future__ import annotations

from typing import Any

from app.config.settings import Settings
from app.security.redaction import sanitize_error
from app.services.sql_database_service import SQLDatabaseService


class SQLDatabaseInventoryRepository:
    def __init__(self, sql_database: SQLDatabaseService, settings: Settings) -> None:
        self.sql_database = sql_database
        self.settings = settings

    async def inventory(self) -> dict[str, Any]:
        if not self.sql_database.configured:
            return {
                "database": self.settings.baleshop_database_label,
                "engine": "mysql",
                "configured": False,
                "error": "BALESHOP_DATABASE_URL is not configured.",
                "backend_discovery": {
                    "source": "/Users/kofibright/Desktop/TriciaBales/baleshop",
                    "configured_local_database": "bale_shop",
                    "requested_database_label": self.settings.baleshop_database_label,
                },
            }

        tables = await self.sql_database.list_tables()
        table_summaries = []
        for table_name in tables:
            summary: dict[str, Any] = {"table": table_name}
            try:
                summary["count"] = await self.sql_database.table_count(table_name)
            except Exception as exc:
                summary["count_error"] = sanitize_error(exc)
            try:
                storage = await self.sql_database.table_storage(table_name)
                summary["storage"] = storage
            except Exception as exc:
                summary["storage_error"] = sanitize_error(exc)
            try:
                summary["index_count"] = len(await self.sql_database.table_indexes(table_name))
            except Exception as exc:
                summary["index_error"] = sanitize_error(exc)
            table_summaries.append(summary)

        return {
            "database": self.sql_database.database_name,
            "label": self.settings.baleshop_database_label,
            "engine": "mysql",
            "configured": True,
            "table_count": len(tables),
            "tables": table_summaries,
        }
