from __future__ import annotations

from fastapi import APIRouter
from fastapi import Request

from app.models.health import HealthResponse


router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    orchestrator = request.app.state.orchestrator
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        agents=orchestrator.registry.names(),
    )
