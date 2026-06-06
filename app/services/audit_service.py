from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class AuditService:
    def __init__(
        self,
        *,
        repository_agent: BaseAgent,
        vector_search_agent: BaseAgent,
        database_agent: BaseAgent,
    ) -> None:
        self.repository_agent = repository_agent
        self.vector_search_agent = vector_search_agent
        self.database_agent = database_agent

    async def run_audit(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        normalized = query.lower()
        if "security" in normalized:
            return await self.security_audit(query, context)
        if "architecture" in normalized:
            return await self.architecture_audit(query, context)
        if "api" in normalized:
            return await self.api_audit(query, context)
        if "quality" in normalized or "code quality" in normalized:
            return await self.code_quality_audit(query, context)

        findings: list[dict[str, str]] = []
        findings.extend(await self.security_audit(query, context))
        findings.extend(await self.architecture_audit(query, context))
        findings.extend(await self.api_audit(query, context))
        findings.extend(await self.code_quality_audit(query, context))
        return findings

    async def security_audit(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        response = await self.vector_search_agent.execute(
            query=f"Find hardcoded secrets API keys exposed tokens unsafe environment handling. {query}",
            context=context,
        )
        findings: list[dict[str, str]] = []
        for match in response.result.get("matches", []) if response.success else []:
            snippet = str(match.get("snippet") or "")
            lowered = snippet.lower()
            if any(token in lowered for token in ("api_key", "apikey", "secret", "token", "password", "bearer ")):
                findings.append(
                    self._finding(
                        severity="HIGH",
                        category="Security",
                        issue=f"Potential hardcoded secret or token in {self._location(match)}.",
                        recommendation="Move secrets to managed environment configuration and rotate any exposed credentials.",
                    )
                )
        return findings or [
            self._finding(
                severity="LOW",
                category="Security",
                issue="No obvious hardcoded secrets were detected in semantic matches.",
                recommendation="Run credential scanning in CI for deterministic coverage.",
            )
        ]

    async def architecture_audit(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        inventory_response = await self.repository_agent.execute(query="Show repository inventory", context=context)
        search_response = await self.vector_search_agent.execute(
            query=f"Find circular dependencies oversized modules duplicated responsibilities. {query}",
            context=context,
        )
        findings: list[dict[str, str]] = []
        for repository in inventory_response.result.get("repositories", []) if inventory_response.success else []:
            chunk_count = int(repository.get("chunk_count") or 0)
            if chunk_count >= int(context.get("oversized_chunk_threshold", 500)):
                findings.append(
                    self._finding(
                        severity="MEDIUM",
                        category="Architecture",
                        issue=f"Repository {repository.get('repository')} has a large indexed surface with {chunk_count} chunks.",
                        recommendation="Review module boundaries and split oversized responsibilities into smaller packages.",
                    )
                )
        for match in search_response.result.get("matches", []) if search_response.success else []:
            snippet = str(match.get("snippet") or "").lower()
            if "circular" in snippet or "duplicate" in snippet or "responsibilit" in snippet:
                findings.append(
                    self._finding(
                        severity="MEDIUM",
                        category="Architecture",
                        issue=f"Potential architecture concern in {self._location(match)}.",
                        recommendation="Trace dependencies and clarify ownership boundaries before expanding the module.",
                    )
                )
        return findings or [
            self._finding(
                severity="LOW",
                category="Architecture",
                issue="No clear architecture risks were detected from repository inventory and semantic matches.",
                recommendation="Validate dependency graphs with static tooling for circular imports.",
            )
        ]

    async def api_audit(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        response = await self.vector_search_agent.execute(
            query=f"Find API routes missing validation inconsistent responses duplicate routes. {query}",
            context=context,
        )
        findings: list[dict[str, str]] = []
        for match in response.result.get("matches", []) if response.success else []:
            snippet = str(match.get("snippet") or "").lower()
            if any(token in snippet for token in ("request", "route", "router", "endpoint", "validation", "response")):
                findings.append(
                    self._finding(
                        severity="MEDIUM",
                        category="API",
                        issue=f"API implementation in {self._location(match)} should be checked for validation and response consistency.",
                        recommendation="Add request models, shared response envelopes, and route duplication tests.",
                    )
                )
        return findings or [
            self._finding(
                severity="LOW",
                category="API",
                issue="No obvious API validation or response issues were detected in semantic matches.",
                recommendation="Add contract tests for critical API routes.",
            )
        ]

    async def code_quality_audit(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        db_response = await self.database_agent.execute(query="What are the top repositories by chunk count?", context=context)
        search_response = await self.vector_search_agent.execute(
            query=f"Find duplicate logic dead code oversized files missing error handling. {query}",
            context=context,
        )
        findings: list[dict[str, str]] = []
        for repository in db_response.result.get("top_repositories", []) if db_response.success else []:
            chunk_count = int(repository.get("chunk_count") or 0)
            if chunk_count >= int(context.get("quality_chunk_threshold", 500)):
                findings.append(
                    self._finding(
                        severity="MEDIUM",
                        category="Code Quality",
                        issue=f"{repository.get('repository')} has {chunk_count} indexed chunks, which may indicate oversized areas.",
                        recommendation="Prioritize hotspot review for duplicate logic, dead code, and missing error handling.",
                    )
                )
        for match in search_response.result.get("matches", []) if search_response.success else []:
            snippet = str(match.get("snippet") or "").lower()
            if any(token in snippet for token in ("todo", "fixme", "except pass", "duplicate", "dead code", "error")):
                findings.append(
                    self._finding(
                        severity="MEDIUM",
                        category="Code Quality",
                        issue=f"Potential code quality issue in {self._location(match)}.",
                        recommendation="Refactor duplicated or dead paths and add explicit error handling.",
                    )
                )
        return findings or [
            self._finding(
                severity="LOW",
                category="Code Quality",
                issue="No obvious code quality issues were detected from available signals.",
                recommendation="Supplement semantic review with static analysis and coverage reports.",
            )
        ]

    def _location(self, match: dict[str, Any]) -> str:
        repository = match.get("repository") or "unknown repository"
        file_path = match.get("file_path") or "unknown file"
        return f"{repository}/{file_path}"

    def _finding(self, *, severity: str, category: str, issue: str, recommendation: str) -> dict[str, str]:
        return {
            "severity": severity,
            "category": category,
            "issue": issue,
            "recommendation": recommendation,
        }
