from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Annotated

from app.models.health import HealthResponse
from app.models.health import ReadinessResponse
from app.security.auth import AuthenticatedPrincipal
from app.security.auth import require_role
from app.security.redaction import sanitize_error


router = APIRouter(tags=["Health"])
ViewerPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_role("viewer"))]
AdminPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_role("admin"))]


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, principal: ViewerPrincipal) -> HealthResponse:
    settings = request.app.state.settings
    orchestrator = request.app.state.orchestrator
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        registered_agents=len(orchestrator.registry.names()),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def ready(request: Request, principal: AdminPrincipal) -> JSONResponse:
    checks = {
        "mongodb": await _run_check(request.app.state.mongodb.ping),
        "vertex_ai": await _run_check(request.app.state.embedding_service.readiness_check),
        "cloud_run": await _run_check(request.app.state.cloudrun_service.readiness_check),
        "cloud_logging": await _run_check(request.app.state.observability_service.readiness_check),
    }
    status = "ready" if all(check["ok"] for check in checks.values()) else "not_ready"
    return JSONResponse(
        status_code=200 if status == "ready" else 503,
        content=ReadinessResponse(status=status, checks=checks).model_dump(),
    )


async def _run_check(check):
    try:
        await check()
        return {"ok": True, "error": None}
    except Exception as exc:
        return {"ok": False, "error": sanitize_error(exc)}
