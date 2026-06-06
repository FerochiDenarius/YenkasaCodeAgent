from __future__ import annotations

from fastapi import APIRouter
from fastapi import Request

from app.core.orchestrator import YenkasaCodeOrchestrator
from app.models.agent import AgentDescriptor
from app.models.agent import AgentQueryRequest
from app.models.agent import AgentResponse
from app.models.metrics import AgentMetricsResponse


router = APIRouter(prefix="/api/agent", tags=["Agent"])


def get_orchestrator(request: Request) -> YenkasaCodeOrchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        orchestrator = YenkasaCodeOrchestrator()
        request.app.state.orchestrator = orchestrator
    return orchestrator


@router.get("/agents", response_model=list[AgentDescriptor])
async def list_agents(request: Request) -> list[AgentDescriptor]:
    return get_orchestrator(request).discover_agents()


@router.get("/metrics", response_model=AgentMetricsResponse)
async def agent_metrics(request: Request) -> AgentMetricsResponse:
    return await get_orchestrator(request).get_metrics()


@router.post("/query", response_model=AgentResponse)
async def query_agent(payload: AgentQueryRequest, request: Request) -> AgentResponse:
    return await get_orchestrator(request).route(payload)
