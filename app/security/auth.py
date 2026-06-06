from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Annotated
from typing import Callable

from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request

from app.models.agent import AgentQueryRequest
from app.orchestrator import IntentClassifier


ROLE_RANK = {"viewer": 1, "developer": 2, "admin": 3}
AGENT_ROLES = {
    "system": "viewer",
    "VectorSearchAgent": "viewer",
    "RepositoryAgent": "developer",
    "CodeAuditAgent": "developer",
    "RefactorAgent": "developer",
    "ProductBuilderAgent": "developer",
    "DatabaseAgent": "admin",
    "CloudRunAgent": "admin",
    "ObservabilityAgent": "admin",
}
INTENT_ROLES = {
    "search": "viewer",
    "repository": "developer",
    "audit": "developer",
    "refactor": "developer",
    "product_builder": "developer",
    "database": "admin",
    "deployment": "admin",
    "observability": "admin",
}


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    role: str
    key_hash: str


def _configured_keys(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    configured = {
        settings.admin_api_key: "admin",
        settings.developer_api_key: "developer",
        settings.viewer_api_key: "viewer",
    }
    for item in settings.api_keys.split(","):
        if not item.strip() or ":" not in item:
            continue
        role, key = item.split(":", 1)
        role = role.strip().lower()
        key = key.strip()
        if role in ROLE_RANK and key:
            configured[key] = role
    return {key: role for key, role in configured.items() if key}


async def authenticate_request(request: Request) -> AuthenticatedPrincipal:
    supplied_key = request.headers.get("X-API-Key", "")
    if not supplied_key:
        raise HTTPException(status_code=401, detail="Missing API key.")
    for configured_key, role in _configured_keys(request).items():
        if secrets.compare_digest(supplied_key, configured_key):
            key_hash = hashlib.sha256(supplied_key.encode("utf-8")).hexdigest()
            return AuthenticatedPrincipal(role=role, key_hash=key_hash)
    raise HTTPException(status_code=401, detail="Invalid API key.")


def _assert_role(principal: AuthenticatedPrincipal, required_role: str) -> None:
    if ROLE_RANK[principal.role] < ROLE_RANK[required_role]:
        raise HTTPException(status_code=403, detail="Insufficient role.")


def require_role(required_role: str) -> Callable[[Annotated[AuthenticatedPrincipal, Depends(authenticate_request)]], AuthenticatedPrincipal]:
    async def dependency(
        principal: Annotated[AuthenticatedPrincipal, Depends(authenticate_request)],
    ) -> AuthenticatedPrincipal:
        _assert_role(principal, required_role)
        return principal

    return dependency


def required_role_for_query(payload: AgentQueryRequest) -> str:
    if payload.agent:
        return AGENT_ROLES.get(payload.agent, "developer")
    intents = IntentClassifier().classify(payload.query)
    roles = [INTENT_ROLES.get(intent, "viewer") for intent in intents if intent != "multi-agent"]
    if not roles:
        return "viewer"
    return max(roles, key=lambda role: ROLE_RANK[role])


def require_query_authorization(payload: AgentQueryRequest, principal: AuthenticatedPrincipal) -> str:
    required_role = required_role_for_query(payload)
    _assert_role(principal, required_role)
    return required_role
