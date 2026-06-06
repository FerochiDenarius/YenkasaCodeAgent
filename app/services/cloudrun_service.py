from __future__ import annotations

from typing import Any

from app.config.settings import Settings


class CloudRunService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._services_client: Any | None = None

    def _get_services_client(self) -> Any:
        if self._services_client is None:
            try:
                from google.cloud import run_v2
            except ImportError as exc:
                raise RuntimeError("google-cloud-run is required for Cloud Run access.") from exc
            self._services_client = run_v2.ServicesAsyncClient()
        return self._services_client

    def _service_name(self) -> str:
        if not self.settings.google_cloud_project:
            raise RuntimeError("GOOGLE_CLOUD_PROJECT is not configured.")
        if not self.settings.cloud_run_service:
            raise RuntimeError("CLOUD_RUN_SERVICE is not configured.")
        return (
            f"projects/{self.settings.google_cloud_project}/locations/{self.settings.vertex_location}/"
            f"services/{self.settings.cloud_run_service}"
        )

    async def service_status(self) -> dict[str, Any]:
        service = await self._get_services_client().get_service(name=self._service_name())
        return {
            "service": service.name,
            "url": getattr(service, "uri", None),
            "latest_ready_revision": getattr(service, "latest_ready_revision", None),
            "latest_created_revision": getattr(service, "latest_created_revision", None),
            "traffic": self._traffic_allocations(getattr(service, "traffic", [])),
            "healthy": self._is_healthy(service),
        }

    async def revision_status(self) -> dict[str, Any]:
        status = await self.service_status()
        return {
            "service": status["service"],
            "live_revision": self._live_revision(status["traffic"]) or status["latest_ready_revision"],
            "latest_ready_revision": status["latest_ready_revision"],
            "latest_created_revision": status["latest_created_revision"],
        }

    async def traffic_allocation(self) -> dict[str, Any]:
        status = await self.service_status()
        return {"service": status["service"], "traffic": status["traffic"]}

    async def deployment_history(self) -> dict[str, Any]:
        status = await self.service_status()
        return {
            "service": status["service"],
            "revisions": [
                {
                    "revision": status["latest_ready_revision"],
                    "state": "READY",
                },
                {
                    "revision": status["latest_created_revision"],
                    "state": "CREATED",
                },
            ],
        }

    async def deployment_health(self) -> dict[str, Any]:
        status = await self.service_status()
        return {
            "service": status["service"],
            "healthy": status["healthy"],
            "latest_ready_revision": status["latest_ready_revision"],
            "traffic": status["traffic"],
        }

    def _traffic_allocations(self, traffic: Any) -> list[dict[str, Any]]:
        allocations = []
        for target in traffic:
            allocations.append(
                {
                    "revision": getattr(target, "revision", None),
                    "percent": getattr(target, "percent", 0),
                    "tag": getattr(target, "tag", None),
                }
            )
        return allocations

    def _live_revision(self, traffic: list[dict[str, Any]]) -> str | None:
        for target in traffic:
            if int(target.get("percent") or 0) > 0:
                return target.get("revision")
        return None

    def _is_healthy(self, service: Any) -> bool:
        latest_ready_revision = getattr(service, "latest_ready_revision", None)
        traffic = self._traffic_allocations(getattr(service, "traffic", []))
        return bool(latest_ready_revision and any(int(target.get("percent") or 0) > 0 for target in traffic))
