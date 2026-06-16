from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.agent import AgentResponse
from app.utils.evidence_package import build_evidence_package


class ReasoningEngine:
    model = "yenkasa_code_reasoning_v1"

    def finalize_response(self, *, query: str, response: AgentResponse) -> AgentResponse:
        evidence_package = response.evidence_package or build_evidence_package(
            agent=response.agent,
            result=response.result,
            success=response.success,
            error=response.error,
            query=query,
        )
        if response.agent == "YIO":
            result = self._finalize_yio(query=query, response=response, evidence_package=evidence_package)
        else:
            result = self._finalize_single_agent(query=query, response=response, evidence_package=evidence_package)
        return response.model_copy(
            update={
                "result": result,
                "evidence_package": evidence_package,
                "reasoning": {
                    "model": self.model,
                    "finalized": True,
                    "raw_result_available": False,
                },
            }
        )

    def _finalize_yio(self, *, query: str, response: AgentResponse, evidence_package: dict[str, Any]) -> dict[str, Any]:
        result = response.result
        packages = [item for item in result.get("agent_results", []) if isinstance(item, dict)]
        findings = result.get("findings") or []
        recommendations = result.get("recommendations") or []
        evidence = result.get("evidence") or []
        answer = self._repository_yio_answer(query=query, result=result, packages=packages)
        if answer is None:
            answer = self._code_inspection_yio_answer(query=query, result=result, packages=packages)
        if answer is None:
            parts = [f"I checked {len(packages)} agent(s) for this request."]
            if not response.success:
                parts.append("One or more planned agents failed, so this is a partial answer.")
            if findings:
                first = findings[0]
                issue = first.get("issue") if isinstance(first, dict) else str(first)
                parts.append(f"Most important finding: {issue}.")
            if recommendations:
                first = recommendations[0]
                recommendation = first.get("recommendation") if isinstance(first, dict) else str(first)
                parts.append(f"Recommended next action: {recommendation}.")
            if evidence:
                parts.append(f"I used {len(evidence)} supporting evidence item(s).")
            if len(parts) == 1:
                parts.append("No high-risk finding was produced by the collected evidence.")
            answer = " ".join(parts)
        if not response.success:
            answer += "\n\nOne or more planned agents failed, so this is a partial answer."
        return {
            "answer": answer,
            "summary": answer,
            "plan": result.get("plan", {}),
            "findings": findings,
            "evidence": evidence,
            "facts": {
                "agent_count": len(packages),
                "plan": result.get("plan", {}),
                "finding_count": len(findings),
                "recommendation_count": len(recommendations),
                "evidence_count": len(evidence),
            },
            "sources": evidence,
            "recommendations": recommendations,
            "confidence": evidence_package.get("confidence", 0.0),
            "agent_results": packages,
        }

    def _repository_yio_answer(
        self,
        *,
        query: str,
        result: dict[str, Any],
        packages: list[dict[str, Any]],
    ) -> str | None:
        repository_package = self._package_for_agent(packages, "RepositoryAgent")
        vector_package = self._package_for_agent(packages, "VectorSearchAgent")
        evidence = [item for item in result.get("evidence") or [] if isinstance(item, dict)]
        code_sources = self._code_sources(evidence)
        if not repository_package and not vector_package and not code_sources:
            return None

        facts = repository_package.get("facts", {}) if repository_package else {}
        repository_count = self._int(facts, "repository_count")
        total_files = self._int(facts, "total_files")
        total_chunks = self._int(facts, "total_chunks")
        latest = facts.get("latest_repository") if isinstance(facts.get("latest_repository"), dict) else None
        names = facts.get("repository_names") if isinstance(facts.get("repository_names"), list) else []
        lowered = query.lower()
        is_specific_code_question = any(
            token in lowered
            for token in (
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
        )

        if code_sources:
            relevant = self._rank_sources_for_query(query=query, sources=code_sources)
            if relevant:
                heroku_terms = ("heroku", "procfile", "dyno", "app.json")
                heroku_sources = [item for item in relevant if any(term in self._source_text(item) for term in heroku_terms)]
                if "heroku" in lowered and not heroku_sources:
                    lines = ["I found file-level evidence for the call/video-call server code, but I did not find file-level evidence that it is hosted on Heroku."]
                    lines.append("The strongest matches point to signaling/call handling, not deployment hosting config.")
                else:
                    lines = ["I checked the indexed repository source and found file-level evidence."]
                if heroku_sources:
                    lines.append("There are Heroku-related signals in the indexed files.")
                for item in relevant[:5]:
                    lines.append(f"- {self._source_label(item)}")
                if repository_count:
                    lines.append(f"Repository coverage used for this search: {repository_count} repositories, {total_files:,} files, {total_chunks:,} chunks.")
                return "\n".join(lines)
            lines = ["I searched the indexed repository source, but I did not find a strong file-level match for this exact question."]
            if code_sources:
                lines.append("Closest indexed matches:")
                lines.extend(f"- {self._source_label(item)}" for item in code_sources[:3])
            if repository_count:
                lines.append(f"The snapshots are available: {repository_count} repositories, {total_files:,} files, {total_chunks:,} chunks.")
            return "\n".join(lines)

        if repository_package and is_specific_code_question:
            if vector_package:
                lines = ["I can see indexed repository snapshots and I also ran source search, but the searchable index returned no file-level matches for this exact question."]
                lines.append("I do not have evidence from indexed files proving where the call or video-call server is hosted.")
            else:
                lines = ["I can see indexed repository snapshots, but this response only contains repository inventory."]
                lines.append("I do not yet have file-level evidence proving where the call or video-call server is hosted.")
            if latest:
                lines.append(f"Latest indexed repository: {latest.get('repository')} on {latest.get('latest_indexed_at')}.")
            if repository_count:
                lines.append(f"Available repository coverage: {repository_count} repositories, {total_files:,} files, {total_chunks:,} chunks.")
            if vector_package:
                lines.append("This usually means the relevant Heroku, Procfile, WebSocket, signaling, or call-server files were not indexed or were not captured in the active searchable repository chunks.")
            else:
                lines.append("For this question, RepositoryAgent must be paired with VectorSearchAgent so it can search files like Procfile, app.json, package scripts, WebSocket/signaling server code, and Heroku config.")
            return "\n".join(lines)

        if repository_package:
            lines = [f"I know about {repository_count} indexed repositor{'y' if repository_count == 1 else 'ies'}."]
            if total_files or total_chunks:
                lines.append(f"Coverage: {total_files:,} files and {total_chunks:,} chunks.")
            if latest:
                lines.append(f"Most recent indexing activity: {latest.get('repository')} on {latest.get('latest_indexed_at')}.")
            if names:
                rendered = [str(name) for name in names if str(name).strip()]
                lines.append("Repositories: " + ", ".join(rendered[:12]) + ("." if len(rendered) <= 12 else ", and more."))
            return "\n".join(lines)
        return None

    def _code_inspection_yio_answer(
        self,
        *,
        query: str,
        result: dict[str, Any],
        packages: list[dict[str, Any]],
    ) -> str | None:
        vector_package = self._package_for_agent(packages, "VectorSearchAgent")
        evidence = [item for item in result.get("evidence") or [] if isinstance(item, dict)]
        code_sources = self._code_sources(evidence)
        if not vector_package and not code_sources:
            return None
        if not code_sources:
            return "I searched the indexed source, but I did not find strong matching files for this question."
        relevant = self._rank_sources_for_query(query=query, sources=code_sources)
        lines = [f"I found {len(code_sources)} indexed source match(es)."]
        for item in relevant[:5]:
            lines.append(f"- {self._source_label(item)}")
        return "\n".join(lines)

    def _finalize_single_agent(self, *, query: str, response: AgentResponse, evidence_package: dict[str, Any]) -> dict[str, Any]:
        answer = self._answer_for_agent(query=query, agent=response.agent, result=response.result, success=response.success, error=response.error)
        return {
            "answer": answer,
            "summary": answer,
            "facts": evidence_package.get("facts", {}),
            "sources": evidence_package.get("sources", []),
            "recommendations": evidence_package.get("recommendations", []),
            "confidence": evidence_package.get("confidence", 0.0),
        }

    def _answer_for_agent(
        self,
        *,
        query: str,
        agent: str,
        result: dict[str, Any],
        success: bool,
        error: str | None,
    ) -> str:
        if not success:
            return f"{agent} could not collect evidence for this request. Error: {error or 'unknown failure'}."
        if agent == "RepositoryAgent":
            return self._repository_answer(query, result)
        if agent == "DatabaseAgent":
            return self._database_answer(result)
        if agent == "VectorSearchAgent":
            return self._vector_answer(result)
        if agent == "ObservabilityAgent":
            return self._observability_answer(result)
        if agent == "CloudRunAgent":
            return self._cloudrun_answer(result)
        if "findings" in result:
            findings = result.get("findings") or []
            if findings:
                first = findings[0]
                issue = first.get("issue") if isinstance(first, dict) else str(first)
                return f"I found {len(findings)} issue(s). Highest-signal finding: {issue}."
            return "I completed the audit and did not find high-signal issues in the collected evidence."
        if "recommendations" in result:
            recommendations = result.get("recommendations") or []
            if recommendations:
                first = recommendations[0]
                text = first.get("recommendation") if isinstance(first, dict) else str(first)
                return f"I found {len(recommendations)} recommendation(s). Priority recommendation: {text}."
            return "I did not find actionable recommendations in the collected evidence."
        return self._generic_answer(result)

    def _repository_answer(self, query: str, result: dict[str, Any]) -> str:
        matches = [match for match in result.get("matches") or [] if isinstance(match, dict)]
        if matches:
            relevant = self._rank_sources_for_query(query=query, sources=matches)
            lines = [f"I searched the indexed repository content and found {len(matches)} file-level match(es)."]
            if self._asks_for_explanation(query):
                lines.append("The strongest matching files indicate where the requested behavior is implemented.")
            for item in relevant[:5]:
                lines.append(f"- {self._source_label(item)}")
            return "\n".join(lines)
        if self._is_repository_content_query(query) and "search" in result:
            return "I searched the indexed repository content, but I did not find a strong file-level match for this question."

        repositories = self._repository_rows(result)
        lowered = query.lower()
        if repositories:
            total_files = sum(self._int(row, "file_count", "files", "total_files") for row in repositories)
            total_chunks = sum(self._int(row, "chunk_count", "chunks", "total_chunks") for row in repositories)
            latest = self._latest_repository(repositories)
            names = [self._repo_name(row) for row in repositories if self._repo_name(row)]
            if "scan" in lowered or "snapshot" in lowered or "see my repo" in lowered:
                lines = ["I can see indexed repository snapshots."]
                if latest:
                    lines.append(f"Latest indexed repository: {latest['name']} on {latest['timestamp']}.")
                lines.append("I do not see evidence of an active scan currently running.")
            else:
                lines = [f"I know about {len(repositories)} indexed repositor{'y' if len(repositories) == 1 else 'ies'}."]
                if total_files or total_chunks:
                    lines.append(f"Coverage: {total_files:,} files and {total_chunks:,} chunks.")
                if latest:
                    lines.append(f"Most recent indexing activity: {latest['name']} on {latest['timestamp']}.")
            if names:
                lines.append("Repositories: " + ", ".join(names[:12]) + ("." if len(names) <= 12 else ", and more."))
            return "\n".join(lines)
        if "top_repositories" in result:
            rows = result.get("top_repositories") or []
            if rows:
                top = rows[0]
                return f"The largest indexed repository is {self._repo_name(top)} with {self._int(top, 'chunk_count', 'chunks'):,} chunks."
        if "language_breakdown" in result:
            rows = result.get("language_breakdown") or []
            if rows:
                parts = [f"{row.get('language')}: {self._int(row, 'file_count'):,} files, {self._int(row, 'chunk_count'):,} chunks" for row in rows[:6]]
                return "Repository language coverage: " + "; ".join(parts) + "."
        if "latest_repository_activity" in result:
            row = result["latest_repository_activity"]
            return f"Latest indexed file: {row.get('repository')} {row.get('file_path')} at {row.get('indexed_at')}."
        if "repository_health" in result:
            health = result["repository_health"]
            missing = self._int(health, "missing_metadata_count") if isinstance(health, dict) else 0
            zero = len(health.get("zero_chunk_repositories") or []) if isinstance(health, dict) else 0
            return f"Repository health check completed: {missing} chunks missing metadata and {zero} zero-chunk repositories."
        return self._generic_answer(result)

    def _database_answer(self, result: dict[str, Any]) -> str:
        if "count" in result and result.get("alias"):
            return f"{result['alias']} currently has {int(result.get('count') or 0):,} document(s)."
        if "repo_chunks_count" in result or "memory_embeddings_count" in result:
            return (
                f"Database evidence collected: repo chunks={int(result.get('repo_chunks_count') or 0):,}, "
                f"memory embeddings={int(result.get('memory_embeddings_count') or 0):,}."
            )
        if "databases" in result or "database_inventory" in result:
            return "Database inventory was collected. I summarized the schema/count evidence without exposing raw rows."
        if "database_health" in result:
            health = result["database_health"]
            risks = len(health.get("query_pattern_risks") or []) if isinstance(health, dict) else 0
            missing = len(health.get("missing_indexes") or []) if isinstance(health, dict) else 0
            return f"Database health evidence collected: {missing} missing-index finding(s), {risks} query-risk finding(s)."
        return self._generic_answer(result)

    def _vector_answer(self, result: dict[str, Any]) -> str:
        matches = result.get("matches") or []
        if not matches:
            return "I searched indexed repository evidence but did not find strong matches."
        first = matches[0]
        return (
            f"I found {len(matches)} relevant indexed source match(es). "
            f"Top match: {first.get('repository')} {first.get('file_path')}."
        )

    def _observability_answer(self, result: dict[str, Any]) -> str:
        summary = result.get("error_summary") or result.get("log_summary") or {}
        if isinstance(summary, dict):
            count = summary.get("error_count") or summary.get("log_count") or summary.get("count") or 0
            incident = summary.get("incident_detected")
            if incident is not None:
                return f"Observability evidence shows {int(count or 0):,} recent error(s). Incident detected: {'yes' if incident else 'no'}."
            return f"Observability evidence collected {int(count or 0):,} recent log item(s)."
        return self._generic_answer(result)

    def _cloudrun_answer(self, result: dict[str, Any]) -> str:
        status = result.get("service_status") or result.get("deployment_health") or result.get("live_revision") or {}
        if isinstance(status, dict):
            healthy = status.get("healthy")
            revision = status.get("latest_ready_revision") or status.get("revision") or status.get("name")
            if healthy is not None or revision:
                return f"Cloud Run evidence collected. Healthy: {'yes' if healthy else 'no'}. Latest ready revision: {revision or 'unknown'}."
        return self._generic_answer(result)

    def _generic_answer(self, result: dict[str, Any]) -> str:
        keys = [key for key in result if not key.startswith("_") and key not in {"execution_time_ms"}]
        if not keys:
            return "I collected evidence, but there was no additional detail to summarize."
        return "I collected evidence for: " + ", ".join(keys[:6]) + "."

    @staticmethod
    def _package_for_agent(packages: list[dict[str, Any]], agent: str) -> dict[str, Any] | None:
        for package in packages:
            if str(package.get("agent") or "") == agent:
                return package
        return None

    @staticmethod
    def _code_sources(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        sources = []
        for item in items:
            if item.get("file_path") or item.get("snippet"):
                sources.append(item)
            for nested in item.get("sources") or []:
                if isinstance(nested, dict) and (nested.get("file_path") or nested.get("snippet")):
                    sources.append(nested)
        seen: set[tuple[str, str, str]] = set()
        unique = []
        for source in sources:
            key = (
                str(source.get("repository") or ""),
                str(source.get("file_path") or ""),
                str(source.get("snippet") or "")[:120],
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(source)
        return unique

    def _rank_sources_for_query(self, *, query: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        query_terms = self._query_terms(query)
        def score(source: dict[str, Any]) -> tuple[int, float]:
            text = self._source_text(source)
            keyword_score = sum(1 for term in query_terms if term in text)
            try:
                similarity = float(source.get("similarity_score") or source.get("score") or 0.0)
            except (TypeError, ValueError):
                similarity = 0.0
            return (keyword_score, similarity)

        return sorted(sources, key=score, reverse=True)

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        lowered = query.lower()
        terms = [
            "cloudinary",
            "upload",
            "uploads",
            "gcs",
            "google cloud storage",
            "agora",
            "livestream",
            "moderation",
            "heroku",
            "procfile",
            "dyno",
            "call",
            "video",
            "signaling",
            "signalling",
            "websocket",
            "socket.io",
            "socketio",
            "server",
        ]
        return [term for term in terms if term in lowered]

    @staticmethod
    def _is_repository_content_query(query: str) -> bool:
        lowered = query.lower()
        return any(
            term in lowered
            for term in (
                "which file",
                "what file",
                "where is",
                "find",
                "search",
                "locate",
                "explain",
                "cloudinary",
                "upload",
                "agora",
                "livestream",
                "moderation",
                "heroku",
                "procfile",
                "websocket",
                "socket.io",
                "socketio",
            )
        )

    @staticmethod
    def _asks_for_explanation(query: str) -> bool:
        lowered = query.lower()
        return "explain" in lowered or "how" in lowered or "what does" in lowered

    @staticmethod
    def _source_text(source: dict[str, Any]) -> str:
        return " ".join(
            str(source.get(key) or "")
            for key in ("repository", "file_path", "snippet", "summary", "message")
        ).lower()

    @staticmethod
    def _source_label(source: dict[str, Any]) -> str:
        repository = str(source.get("repository") or "unknown repository")
        file_path = str(source.get("file_path") or "unknown file")
        snippet = str(source.get("snippet") or "").strip().replace("\n", " ")
        if len(snippet) > 180:
            snippet = snippet[:177].rstrip() + "..."
        if snippet:
            return f"{repository} {file_path}: {snippet}"
        return f"{repository} {file_path}"

    @staticmethod
    def _repository_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
        value = result.get("repositories")
        return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []

    @staticmethod
    def _repo_name(row: dict[str, Any]) -> str:
        return str(row.get("repository") or row.get("repo_name") or row.get("name") or row.get("_id") or "").strip()

    @staticmethod
    def _int(row: dict[str, Any], *keys: str) -> int:
        for key in keys:
            try:
                return int(row.get(key) or 0)
            except (TypeError, ValueError):
                continue
        return 0

    def _latest_repository(self, rows: list[dict[str, Any]]) -> dict[str, str] | None:
        latest: tuple[datetime, str, str] | None = None
        for row in rows:
            name = self._repo_name(row)
            timestamp = str(row.get("latest_indexed_at") or row.get("last_indexed_at") or row.get("indexed_at") or "").strip()
            parsed = self._parse_datetime(timestamp)
            if not name or parsed is None:
                continue
            if latest is None or parsed > latest[0]:
                latest = (parsed, name, timestamp)
        if latest is None:
            return None
        return {"name": latest[1], "timestamp": latest[2]}

    @staticmethod
    def _parse_datetime(value: str) -> datetime | None:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.replace(tzinfo=None)
        return parsed
