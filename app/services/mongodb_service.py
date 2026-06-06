from __future__ import annotations

import asyncio
from typing import Any

from app.config.settings import Settings


class MongoDBService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.settings.mongodb_uri:
                raise RuntimeError("MONGODB_URI is not configured.")
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
            except ImportError as exc:
                raise RuntimeError("motor is required for MongoDB access.") from exc
            self._client = AsyncIOMotorClient(
                self.settings.mongodb_uri,
                serverSelectionTimeoutMS=self.settings.mongodb_server_selection_timeout_ms,
                socketTimeoutMS=self.settings.mongodb_socket_timeout_ms,
                maxPoolSize=self.settings.mongodb_max_pool_size,
            )
        return self._client

    def database(self) -> Any:
        return self._get_client()[self.settings.mongodb_database]

    def collection(self, name: str) -> Any:
        return self.database()[name]

    async def ping(self) -> bool:
        await asyncio.wait_for(self.database().command("ping"), timeout=self.settings.external_timeout_seconds)
        return True

    async def count_documents(self, collection_name: str, filter_query: dict[str, Any] | None = None) -> int:
        return await asyncio.wait_for(
            self.collection(collection_name).count_documents(filter_query or {}),
            timeout=self.settings.external_timeout_seconds,
        )

    async def collection_stats(self, collection_name: str) -> dict[str, Any]:
        return await asyncio.wait_for(
            self.database().command("collStats", collection_name),
            timeout=self.settings.external_timeout_seconds,
        )

    async def latest_record(
        self,
        collection_name: str,
        *,
        sort_field: str,
        projection: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        cursor = self.collection(collection_name).find({}, projection).sort(sort_field, -1).limit(1)
        records = await asyncio.wait_for(cursor.to_list(length=1), timeout=self.settings.external_timeout_seconds)
        return records[0] if records else None

    async def aggregate(self, collection_name: str, pipeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        collection = self.collection(collection_name)
        try:
            cursor = collection.aggregate(
                pipeline,
                maxTimeMS=int(self.settings.external_timeout_seconds * 1000),
            )
        except TypeError:
            cursor = collection.aggregate(pipeline)
        return await asyncio.wait_for(
            cursor.to_list(length=self.settings.mongodb_aggregate_limit),
            timeout=self.settings.external_timeout_seconds,
        )

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
