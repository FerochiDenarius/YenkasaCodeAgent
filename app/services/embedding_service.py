from __future__ import annotations

import asyncio

from app.config.settings import Settings


class EmbeddingService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: object | None = None

    def _get_client(self) -> object:
        if self._client is None:
            if not self.settings.vertex_project_id:
                raise RuntimeError("VERTEX_PROJECT_ID is not configured.")
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError("google-genai is required for Vertex AI embeddings.") from exc
            self._client = genai.Client(
                vertexai=True,
                project=self.settings.vertex_project_id,
                location=self.settings.vertex_location,
            )
        return self._client

    async def embed_query(self, text: str) -> list[float]:
        client = self._get_client()
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.embed_content,
                model=self.settings.vertex_embedding_model,
                contents=[text],
            ),
            timeout=self.settings.external_timeout_seconds,
        )
        if not response.embeddings:
            raise RuntimeError("Vertex AI returned no embeddings.")
        return list(response.embeddings[0].values)

    async def readiness_check(self) -> bool:
        await self.embed_query("readiness check")
        return True
