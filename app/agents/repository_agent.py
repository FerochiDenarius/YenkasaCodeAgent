from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent
from app.repositories.repo_chunks_repository import RepoChunksRepository
from app.repositories.repository_intelligence_repository import RepositoryIntelligenceRepository


class RepositoryAgent(BaseAgent):
    name = "RepositoryAgent"
    description = "Repository intelligence agent for indexed repository inventory, content search, size, language, activity, and health."
    capabilities = [
        "repository_inventory",
        "repository_content_search",
        "repository_file_lookup",
        "repository_code_explanation",
        "repository_size_analysis",
        "language_breakdown",
        "recent_repository_activity",
        "repository_health",
    ]

    def __init__(
        self,
        repo_chunks_repository: RepoChunksRepository,
        repository_intelligence_repository: RepositoryIntelligenceRepository,
    ) -> None:
        self.repo_chunks_repository = repo_chunks_repository
        self.repository_intelligence_repository = repository_intelligence_repository

    async def run(self, query: str, context: dict[str, Any]) -> dict[str, Any]:
        normalized = query.lower()
        limit = int(context.get("limit", 5))

        if self._is_content_question(normalized):
            matches = await self.repo_chunks_repository.search_text(query, limit=limit)
            return {
                "matches": [self._normalize_match(match) for match in matches],
                "search": {
                    "query": query,
                    "collection": self.repo_chunks_repository.collection_name,
                    "match_count": len(matches),
                },
            }

        if "missing metadata" in normalized or "zero chunks" in normalized or "anomal" in normalized or "health" in normalized:
            return {"repository_health": await self.repository_intelligence_repository.health_anomalies()}

        if "latest" in normalized or "recent" in normalized or "activity" in normalized or "indexed file" in normalized:
            return {"latest_repository_activity": await self.repository_intelligence_repository.latest_activity()}

        if "kotlin" in normalized:
            return {"language": await self.repository_intelligence_repository.count_files_by_language("kotlin")}

        if "python" in normalized:
            return {"language": await self.repository_intelligence_repository.count_files_by_language("python")}

        if "language breakdown" in normalized or "languages" in normalized:
            return {"language_breakdown": await self.repository_intelligence_repository.language_breakdown()}

        if "most chunks" in normalized or "largest" in normalized or "chunk count" in normalized or "size" in normalized:
            top_limit = int(context.get("limit", 10))
            return {"top_repositories": await self.repo_chunks_repository.top_repositories_by_chunk_count(limit=top_limit)}

        return {"repositories": await self.repository_intelligence_repository.inventory()}

    @staticmethod
    def _is_content_question(normalized: str) -> bool:
        content_terms = (
            "which file",
            "what file",
            "where is",
            "where are",
            "find",
            "search",
            "locate",
            "explain",
            "show code",
            "implementation",
            "handler",
            "handlers",
            "controller",
            "service",
            "route",
            "upload",
            "cloudinary",
            "gcs",
            "google cloud storage",
            "agora",
            "livestream",
            "live stream",
            "moderation",
            "heroku",
            "procfile",
            "dyno",
            "call server",
            "video call",
            "video server",
            "signaling",
            "signalling",
            "websocket",
            "socket.io",
            "socketio",
        )
        return any(term in normalized for term in content_terms)

    @staticmethod
    def _normalize_match(match: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_path": match.get("file_path") or match.get("path"),
            "repository": match.get("repository") or match.get("repo_name"),
            "similarity_score": match.get("score") or match.get("similarity_score"),
            "snippet": match.get("snippet") or match.get("content") or match.get("text"),
        }
