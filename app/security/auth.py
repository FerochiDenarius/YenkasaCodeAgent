from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from typing import Annotated
from typing import Any
from typing import Callable

import httpx
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
    subject: str | None = None
    email: str | None = None
    source: str = "api_key"


def _configured_keys(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    configured: dict[str, str] = {}
    for key, role in (
        (settings.admin_api_key, "admin"),
        (settings.developer_api_key, "developer"),
        (settings.viewer_api_key, "viewer"),
    ):
        if key and (key not in configured or ROLE_RANK[role] > ROLE_RANK[configured[key]]):
            configured[key] = role
    for item in settings.api_keys.split(","):
        if not item.strip() or ":" not in item:
            continue
        role, key = item.split(":", 1)
        role = role.strip().lower()
        key = key.strip()
        if role in ROLE_RANK and key:
            if key not in configured or ROLE_RANK[role] > ROLE_RANK[configured[key]]:
                configured[key] = role
    return {key: role for key, role in configured.items() if key}


async def authenticate_request(request: Request) -> AuthenticatedPrincipal:
    supplied_key = request.headers.get("X-API-Key", "")
    if supplied_key:
        for configured_key, role in _configured_keys(request).items():
            if secrets.compare_digest(supplied_key, configured_key):
                key_hash = hashlib.sha256(supplied_key.encode("utf-8")).hexdigest()
                return AuthenticatedPrincipal(role=role, key_hash=key_hash)
        raise HTTPException(status_code=401, detail="Invalid API key.")

    bearer_token = _bearer_token(request)
    if bearer_token:
        return await _authenticate_yenkasa_ai_token(request, bearer_token)

    raise HTTPException(status_code=401, detail="Missing API key.")


def _bearer_token(request: Request) -> str:
    authorization = request.headers.get("X-Yenkasa-AI-Authorization", "") or request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


async def _authenticate_yenkasa_ai_token(request: Request, token: str) -> AuthenticatedPrincipal:
    settings = request.app.state.settings
    base_url = settings.yenkasa_ai_base_url.rstrip("/")
    if not base_url:
        raise HTTPException(status_code=401, detail="YenkasaAI authentication is not configured.")

    try:
        async with httpx.AsyncClient(timeout=settings.yenkasa_ai_auth_timeout_seconds) as client:
            response = await client.get(f"{base_url}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=401, detail="YenkasaAI authentication failed.") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid YenkasaAI token.")

    try:
        user = response.json()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid YenkasaAI authentication response.") from exc

    role = _role_from_yenkasa_user(user)
    subject = str(user.get("user_id") or user.get("id") or user.get("sub") or "")
    email = str(user.get("email") or "")
    key_hash = hashlib.sha256(f"yenkasa-ai:{subject or email}:{token}".encode("utf-8")).hexdigest()
    return AuthenticatedPrincipal(role=role, key_hash=key_hash, subject=subject or None, email=email or None, source="yenkasa_ai")


def _role_from_yenkasa_user(user: dict[str, Any]) -> str:
    role = str(user.get("role") or "").strip().lower()
    if role in {"admin", "super_admin", "senior_developer"}:
        return "admin"
    if role in {"developer", "maintainer"}:
        return "developer"
    return "viewer"


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
