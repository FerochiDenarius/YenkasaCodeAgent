from __future__ import annotations

import asyncio
import os

import pytest

from app.config.settings import Settings
from app.repositories.vector_search_repository import VectorSearchRepository
from app.services.embedding_service import EmbeddingService
from app.services.mongodb_service import MongoDBService


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Set RUN_INTEGRATION_TESTS=1 with live credentials to run external integration tests.",
)


def test_live_mongodb_ping() -> None:
    settings = Settings()
    service = MongoDBService(settings)
    try:
        assert asyncio.run(service.ping()) is True
    finally:
        asyncio.run(service.close())


def test_live_vector_search_repo_chunks() -> None:
    settings = Settings()
    service = MongoDBService(settings)
    repository = VectorSearchRepository(service)
    try:
        results = asyncio.run(repository.search_repo_chunks(query_vector=[0.0] * 768, limit=1))
    finally:
        asyncio.run(service.close())

    assert isinstance(results, list)


def test_live_vertex_embedding_generation() -> None:
    settings = Settings()
    service = EmbeddingService(settings)

    embedding = asyncio.run(service.embed_query("readiness check"))

    assert embedding
    assert all(isinstance(value, float) for value in embedding)
