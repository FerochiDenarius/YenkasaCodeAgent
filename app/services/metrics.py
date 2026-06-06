from __future__ import annotations

import asyncio

from app.models.metrics import AgentMetricsResponse


class AgentMetrics:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.database_queries_total = 0
        self.database_query_failures = 0
        self.database_query_duration_ms = 0
        self.repository_queries_total = 0
        self.repository_query_failures = 0
        self.repository_query_duration_ms = 0
        self.vector_queries_total = 0
        self.vector_query_failures = 0
        self.vector_query_duration_ms = 0
        self.audit_queries_total = 0
        self.audit_query_failures = 0
        self.audit_query_duration_ms = 0

    async def record(self, *, success: bool) -> None:
        async with self._lock:
            self.total_requests += 1
            if success:
                self.successful_requests += 1
            else:
                self.failed_requests += 1

    async def record_database_query(self, *, success: bool, duration_ms: int) -> None:
        async with self._lock:
            self.database_queries_total += 1
            self.database_query_duration_ms += duration_ms
            if not success:
                self.database_query_failures += 1

    async def record_repository_query(self, *, success: bool, duration_ms: int) -> None:
        async with self._lock:
            self.repository_queries_total += 1
            self.repository_query_duration_ms += duration_ms
            if not success:
                self.repository_query_failures += 1

    async def record_vector_query(self, *, success: bool, duration_ms: int) -> None:
        async with self._lock:
            self.vector_queries_total += 1
            self.vector_query_duration_ms += duration_ms
            if not success:
                self.vector_query_failures += 1

    async def record_audit_query(self, *, success: bool, duration_ms: int) -> None:
        async with self._lock:
            self.audit_queries_total += 1
            self.audit_query_duration_ms += duration_ms
            if not success:
                self.audit_query_failures += 1

    async def snapshot(self, *, registered_agents: list[str]) -> AgentMetricsResponse:
        async with self._lock:
            return AgentMetricsResponse(
                total_requests=self.total_requests,
                successful_requests=self.successful_requests,
                failed_requests=self.failed_requests,
                registered_agents=registered_agents,
                database_queries_total=self.database_queries_total,
                database_query_failures=self.database_query_failures,
                database_query_duration_ms=self.database_query_duration_ms,
                repository_queries_total=self.repository_queries_total,
                repository_query_failures=self.repository_query_failures,
                repository_query_duration_ms=self.repository_query_duration_ms,
                vector_queries_total=self.vector_queries_total,
                vector_query_failures=self.vector_query_failures,
                vector_query_duration_ms=self.vector_query_duration_ms,
                audit_queries_total=self.audit_queries_total,
                audit_query_failures=self.audit_query_failures,
                audit_query_duration_ms=self.audit_query_duration_ms,
            )
