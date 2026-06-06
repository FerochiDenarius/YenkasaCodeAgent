from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "system" in payload["agents"]


def test_agent_query_routes_to_system_agent() -> None:
    with TestClient(app) as client:
        response = client.post("/api/agent/query", json={"query": "status"})

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "agent": "system",
        "success": True,
        "result": {
            "message": "YenkasaCode Agent foundation is online.",
            "query": "status",
            "context": {},
            "phase": "phase_1_foundation",
        },
        "error": None,
    }


def test_agent_discovery() -> None:
    with TestClient(app) as client:
        response = client.get("/api/agent/agents")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["name"] == "system"
