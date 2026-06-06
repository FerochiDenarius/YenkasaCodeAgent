from __future__ import annotations

from pydantic import BaseModel


class AgentMetricsResponse(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    registered_agents: list[str]
    database_queries_total: int
    database_query_failures: int
    database_query_duration_ms: int
    repository_queries_total: int
    repository_query_failures: int
    repository_query_duration_ms: int
    vector_queries_total: int
    vector_query_failures: int
    vector_query_duration_ms: int
    audit_queries_total: int
    audit_query_failures: int
    audit_query_duration_ms: int
    refactor_queries_total: int
    refactor_query_failures: int
    refactor_query_duration_ms: int
    cloudrun_queries_total: int
    cloudrun_query_failures: int
    cloudrun_query_duration_ms: int
    observability_queries_total: int
    observability_query_failures: int
    observability_query_duration_ms: int
