from __future__ import annotations

from typing import Any

from app.agents.base import BaseAgent


class RefactorService:
    def __init__(
        self,
        *,
        code_audit_agent: BaseAgent,
        repository_agent: BaseAgent,
        vector_search_agent: BaseAgent,
    ) -> None:
        self.code_audit_agent = code_audit_agent
        self.repository_agent = repository_agent
        self.vector_search_agent = vector_search_agent

    async def generate_plan(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        normalized = query.lower()
        if "duplicat" in normalized or "repeated" in normalized:
            return await self.duplication_analysis(query, context)
        if "extract" in normalized or "service" in normalized or "controller" in normalized or "route" in normalized:
            return await self.service_extraction_analysis(query, context)
        if "dependency" in normalized or "coupling" in normalized or "circular" in normalized:
            return await self.dependency_analysis(query, context)
        if "architecture" in normalized or "modular" in normalized or "structure" in normalized:
            return await self.architecture_refactor_analysis(query, context)
        return await self.technical_debt_analysis(query, context)

    async def technical_debt_analysis(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        audit_response = await self.code_audit_agent.execute(query=f"Audit repository for technical debt. {query}", context=context)
        recommendations = [
            self._from_finding(finding, default_category="Technical Debt")
            for finding in audit_response.result.get("findings", [])
            if audit_response.success
        ]
        return recommendations or [
            self._recommendation(
                priority="LOW",
                category="Technical Debt",
                issue="No high-signal technical debt findings were available.",
                recommendation="Run a broader audit and static analysis pass before planning large cleanup work.",
                risk="LOW",
            )
        ]

    async def service_extraction_analysis(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        repository_response = await self.repository_agent.execute(query="Show repository inventory", context=context)
        vector_response = await self.vector_search_agent.execute(
            query=f"Find oversized services controllers routes excessive responsibility concentration. {query}",
            context=context,
        )
        recommendations: list[dict[str, str]] = []
        for repository in repository_response.result.get("repositories", []) if repository_response.success else []:
            chunk_count = int(repository.get("chunk_count") or 0)
            if chunk_count >= int(context.get("extraction_chunk_threshold", 500)):
                recommendations.append(
                    self._recommendation(
                        priority="HIGH",
                        category="Service Extraction",
                        issue=f"{repository.get('repository')} has {chunk_count} indexed chunks and may contain oversized services.",
                        recommendation="Identify cohesive responsibilities and propose service boundaries before moving code.",
                        risk="MEDIUM",
                    )
                )
        for match in vector_response.result.get("matches", []) if vector_response.success else []:
            snippet = str(match.get("snippet") or "").lower()
            if any(token in snippet for token in ("service", "controller", "route", "responsibility", "oversized")):
                recommendations.append(
                    self._recommendation(
                        priority="HIGH",
                        category="Service Extraction",
                        issue=f"Responsibility concentration indicator found in {self._location(match)}.",
                        recommendation="Draft an extraction plan with interfaces, ownership boundaries, and tests before implementation.",
                        risk="MEDIUM",
                    )
                )
        return recommendations or [
            self._recommendation(
                priority="LOW",
                category="Service Extraction",
                issue="No oversized service indicators were found in available signals.",
                recommendation="Keep monitoring module size and route/controller growth.",
                risk="LOW",
            )
        ]

    async def duplication_analysis(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        vector_response = await self.vector_search_agent.execute(
            query=f"Find repeated patterns repeated business logic duplicated code blocks. {query}",
            context=context,
        )
        recommendations = []
        for match in vector_response.result.get("matches", []) if vector_response.success else []:
            snippet = str(match.get("snippet") or "").lower()
            if "duplicate" in snippet or "repeated" in snippet or "same logic" in snippet:
                recommendations.append(
                    self._recommendation(
                        priority="MEDIUM",
                        category="Duplication",
                        issue=f"Potential duplicate logic in {self._location(match)}.",
                        recommendation="Create a shared helper or domain service after confirming call-site behavior is identical.",
                        risk="LOW",
                    )
                )
        return recommendations or [
            self._recommendation(
                priority="LOW",
                category="Duplication",
                issue="No repeated logic indicators were found from semantic retrieval.",
                recommendation="Use clone-detection tooling to supplement semantic analysis.",
                risk="LOW",
            )
        ]

    async def dependency_analysis(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        vector_response = await self.vector_search_agent.execute(
            query=f"Find tight coupling circular dependency indicators dependency hotspots. {query}",
            context=context,
        )
        recommendations = []
        for match in vector_response.result.get("matches", []) if vector_response.success else []:
            snippet = str(match.get("snippet") or "").lower()
            if any(token in snippet for token in ("coupling", "circular", "dependency", "import")):
                recommendations.append(
                    self._recommendation(
                        priority="HIGH",
                        category="Dependency",
                        issue=f"Dependency hotspot indicator found in {self._location(match)}.",
                        recommendation="Introduce dependency inversion or interface boundaries around the hotspot.",
                        risk="MEDIUM",
                    )
                )
        return recommendations or [
            self._recommendation(
                priority="LOW",
                category="Dependency",
                issue="No dependency hotspots were found from semantic retrieval.",
                recommendation="Generate an import graph before planning dependency changes.",
                risk="LOW",
            )
        ]

    async def architecture_refactor_analysis(self, query: str, context: dict[str, Any]) -> list[dict[str, str]]:
        audit_response = await self.code_audit_agent.execute(query=f"Architecture audit for refactor planning. {query}", context=context)
        recommendations = [
            self._from_finding(finding, default_category="Architecture")
            for finding in audit_response.result.get("findings", [])
            if audit_response.success
        ]
        recommendations.append(
            self._recommendation(
                priority="MEDIUM",
                category="Architecture",
                issue="Architecture improvements should be planned as explicit proposals, not automatic edits.",
                recommendation="Prioritize service separation, repository patterns, dependency injection, and modularization by risk.",
                risk="LOW",
            )
        )
        return recommendations

    def _from_finding(self, finding: dict[str, Any], *, default_category: str) -> dict[str, str]:
        return self._recommendation(
            priority=self._priority_from_severity(str(finding.get("severity") or "LOW")),
            category=str(finding.get("category") or default_category),
            issue=str(finding.get("issue") or "Audit finding requires refactor planning."),
            recommendation=str(finding.get("recommendation") or "Create a scoped migration plan before implementation."),
            risk=self._risk_from_priority(str(finding.get("severity") or "LOW")),
        )

    def _priority_from_severity(self, severity: str) -> str:
        normalized = severity.upper()
        if normalized in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}:
            return normalized
        return "LOW"

    def _risk_from_priority(self, priority: str) -> str:
        normalized = priority.upper()
        if normalized == "CRITICAL":
            return "HIGH"
        if normalized in {"HIGH", "MEDIUM"}:
            return "MEDIUM"
        return "LOW"

    def _location(self, match: dict[str, Any]) -> str:
        repository = match.get("repository") or "unknown repository"
        file_path = match.get("file_path") or "unknown file"
        return f"{repository}/{file_path}"

    def _recommendation(
        self,
        *,
        priority: str,
        category: str,
        issue: str,
        recommendation: str,
        risk: str,
    ) -> dict[str, str]:
        return {
            "priority": priority,
            "category": category,
            "issue": issue,
            "recommendation": recommendation,
            "risk": risk,
        }
