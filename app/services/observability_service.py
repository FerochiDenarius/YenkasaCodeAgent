from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

from app.config.settings import Settings


class ObservabilityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._logging_client: Any | None = None

    def _get_logging_client(self) -> Any:
        if self._logging_client is None:
            try:
                from google.cloud import logging_v2
            except ImportError as exc:
                raise RuntimeError("google-cloud-logging is required for log access.") from exc
            self._logging_client = logging_v2.Client(project=self.settings.google_cloud_project)
        return self._logging_client

    async def error_summary(self, *, query: str, hours: int = 24) -> dict[str, Any]:
        entries = self._recent_entries(severity="ERROR", query=query, hours=hours)
        return {
            "window_hours": hours,
            "error_count": len(entries),
            "errors": entries,
            "incident_detected": len(entries) >= 5,
        }

    async def log_summary(self, *, query: str, hours: int = 24) -> dict[str, Any]:
        entries = self._recent_entries(severity=None, query=query, hours=hours)
        return {
            "window_hours": hours,
            "log_count": len(entries),
            "logs": entries,
        }

    async def performance_metrics(self, *, query: str, hours: int = 24) -> dict[str, Any]:
        entries = self._recent_entries(severity=None, query=query, hours=hours)
        slow_entries = [entry for entry in entries if "slow" in str(entry.get("message", "")).lower()]
        return {
            "window_hours": hours,
            "request_count": len(entries),
            "slow_request_indicators": len(slow_entries),
            "performance_notes": slow_entries,
        }

    async def request_trends(self, *, query: str, hours: int = 24) -> dict[str, Any]:
        entries = self._recent_entries(severity=None, query=query, hours=hours)
        return {
            "window_hours": hours,
            "request_count": len(entries),
            "trend": "insufficient_data" if not entries else "activity_detected",
        }

    async def incident_detection(self, *, query: str, hours: int = 24) -> dict[str, Any]:
        summary = await self.error_summary(query=query, hours=hours)
        return {
            "incident_detected": summary["incident_detected"],
            "error_count": summary["error_count"],
            "signals": summary["errors"],
        }

    def _recent_entries(self, *, severity: str | None, query: str, hours: int) -> list[dict[str, Any]]:
        if not self.settings.google_cloud_project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is not configured.")
        since = datetime.now(UTC) - timedelta(hours=hours)
        filters = [f'timestamp >= "{since.isoformat()}"']
        if severity is not None:
            filters.append(f"severity >= {severity}")
        if self.settings.cloud_run_service:
            filters.append(f'resource.labels.service_name="{self.settings.cloud_run_service}"')
        if query:
            filters.append(f'textPayload:"{query}"')
        entries = self._get_logging_client().list_entries(filter_=" AND ".join(filters), page_size=20)
        return [
            {
                "timestamp": getattr(entry, "timestamp", None).isoformat()
                if getattr(entry, "timestamp", None)
                else None,
                "severity": getattr(entry, "severity", None),
                "message": getattr(entry, "payload", None),
                "resource": dict(getattr(getattr(entry, "resource", None), "labels", {}) or {}),
            }
            for entry in entries
        ]
