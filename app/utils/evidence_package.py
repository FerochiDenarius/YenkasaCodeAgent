from __future__ import annotations

from typing import Any


def build_evidence_package(
    *,
    agent: str,
    result: dict[str, Any],
    success: bool,
    error: str | None = None,
    query: str = "",
) -> dict[str, Any]:
    return {
        "agent": agent,
        "facts": _facts(result),
        "sources": _sources(result),
        "confidence": 0.96 if success and not error else 0.0,
        "recommendations": _recommendations(result),
        "query": query,
        "success": success,
        "error": error,
    }


def _facts(result: dict[str, Any]) -> dict[str, Any]:
    facts: dict[str, Any] = {}
    for key, value in result.items():
        if key in {"matches", "recommendations", "findings", "evidence", "execution_time_ms"}:
            continue
        if key == "repositories" and isinstance(value, list):
            facts.update(_repository_facts(value))
            continue
        if key in {"database_inventory", "databases", "sql_database_inventory"}:
            facts[key] = _inventory_summary(value)
            continue
        facts[key] = value
    if "findings" in result:
        facts["finding_count"] = len(result.get("findings") or [])
    if "recommendations" in result:
        facts["recommendation_count"] = len(result.get("recommendations") or [])
    if "matches" in result:
        facts["match_count"] = len(result.get("matches") or [])
    return facts


def _repository_facts(rows: list[Any]) -> dict[str, Any]:
    repositories = [row for row in rows if isinstance(row, dict)]
    latest = None
    for row in repositories:
        timestamp = str(row.get("latest_indexed_at") or row.get("indexed_at") or "").strip()
        if not timestamp:
            continue
        name = str(row.get("repository") or row.get("repo_name") or row.get("name") or "").strip()
        if latest is None or timestamp > latest.get("latest_indexed_at", ""):
            latest = {"repository": name, "latest_indexed_at": timestamp}
    return {
        "repository_count": len(repositories),
        "repository_names": [
            str(row.get("repository") or row.get("repo_name") or row.get("name") or "").strip()
            for row in repositories[:20]
            if str(row.get("repository") or row.get("repo_name") or row.get("name") or "").strip()
        ],
        "total_files": sum(_int(row.get("file_count") or row.get("files") or row.get("total_files")) for row in repositories),
        "total_chunks": sum(_int(row.get("chunk_count") or row.get("chunks") or row.get("total_chunks")) for row in repositories),
        "latest_repository": latest,
    }


def _inventory_summary(value: Any) -> dict[str, Any]:
    if isinstance(value, list):
        return {"item_count": len(value)}
    if isinstance(value, dict):
        return {
            "keys": sorted(str(key) for key in value.keys())[:20],
            "item_count": len(value),
        }
    return {"available": value is not None}


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _sources(result: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    for match in result.get("matches") or []:
        if isinstance(match, dict):
            sources.append(
                {
                    "repository": match.get("repository") or match.get("repo_name"),
                    "file_path": match.get("file_path"),
                    "score": match.get("similarity_score") or match.get("score"),
                    "snippet": match.get("snippet") or match.get("excerpt"),
                }
            )
    latest = result.get("latest_repository_activity")
    if isinstance(latest, dict):
        sources.append(
            {
                "repository": latest.get("repository") or latest.get("repo_name"),
                "file_path": latest.get("file_path"),
                "indexed_at": latest.get("indexed_at") or latest.get("updated_at"),
            }
        )
    return [source for source in sources if any(value for value in source.values())]


def _recommendations(result: dict[str, Any]) -> list[Any]:
    recommendations = result.get("recommendations")
    if isinstance(recommendations, list):
        return recommendations
    findings = result.get("findings")
    if not isinstance(findings, list):
        return []
    output = []
    for finding in findings:
        if isinstance(finding, dict) and finding.get("recommendation"):
            output.append({"recommendation": finding["recommendation"], "category": finding.get("category")})
    return output
