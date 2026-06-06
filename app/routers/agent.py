from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from typing import Annotated

from app.core.orchestrator import YenkasaCodeOrchestrator
from app.services.cloudrun_service import CloudRunService
from app.services.embedding_service import EmbeddingService
from app.services.mongodb_service import MongoDBService
from app.services.observability_service import ObservabilityService
from app.models.agent import AgentDescriptor
from app.models.agent import AgentQueryRequest
from app.models.agent import AgentResponse
from app.models.metrics import AgentMetricsResponse
from app.security.auth import AuthenticatedPrincipal
from app.security.auth import require_query_authorization
from app.security.auth import require_role
from app.security.rate_limit import RateLimiter


router = APIRouter(prefix="/api/agent", tags=["Agent"])


def get_orchestrator(request: Request) -> YenkasaCodeOrchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        mongodb = getattr(request.app.state, "mongodb", None)
        if mongodb is None:
            mongodb = MongoDBService(request.app.state.settings)
            request.app.state.mongodb = mongodb
        embedding_service = getattr(request.app.state, "embedding_service", None)
        if embedding_service is None:
            embedding_service = EmbeddingService(request.app.state.settings)
            request.app.state.embedding_service = embedding_service
        cloudrun_service = getattr(request.app.state, "cloudrun_service", None)
        if cloudrun_service is None:
            cloudrun_service = CloudRunService(request.app.state.settings)
            request.app.state.cloudrun_service = cloudrun_service
        observability_service = getattr(request.app.state, "observability_service", None)
        if observability_service is None:
            observability_service = ObservabilityService(request.app.state.settings)
            request.app.state.observability_service = observability_service
        orchestrator = YenkasaCodeOrchestrator(
            mongodb=mongodb,
            embedding_service=embedding_service,
            cloudrun_service=cloudrun_service,
            observability_service=observability_service,
        )
        request.app.state.orchestrator = orchestrator
    return orchestrator


def get_rate_limiter(request: Request) -> RateLimiter:
    rate_limiter = getattr(request.app.state, "rate_limiter", None)
    if rate_limiter is None:
        rate_limiter = RateLimiter(request.app.state.settings)
        request.app.state.rate_limiter = rate_limiter
    return rate_limiter


ViewerPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_role("viewer"))]
AdminPrincipal = Annotated[AuthenticatedPrincipal, Depends(require_role("admin"))]


@router.get("/agents", response_model=list[AgentDescriptor])
async def list_agents(request: Request, principal: ViewerPrincipal) -> list[AgentDescriptor]:
    await get_rate_limiter(request).check(principal.key_hash)
    return get_orchestrator(request).discover_agents()


@router.get("/metrics", response_model=AgentMetricsResponse)
async def agent_metrics(request: Request, principal: AdminPrincipal) -> AgentMetricsResponse:
    await get_rate_limiter(request).check(principal.key_hash)
    return await get_orchestrator(request).get_metrics()


@router.post("/query", response_model=AgentResponse)
async def query_agent(payload: AgentQueryRequest, request: Request, principal: ViewerPrincipal) -> AgentResponse:
    settings = request.app.state.settings
    if len(payload.query) > settings.max_query_length or len(payload.context) > settings.max_context_keys:
        raise HTTPException(status_code=413, detail="Request exceeds configured limits.")
    required_role = require_query_authorization(payload, principal)
    await get_rate_limiter(request).check(principal.key_hash, expensive=required_role in {"developer", "admin"})
    return await get_orchestrator(request).route(payload)
