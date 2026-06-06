from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    payload = response.json()
    assert payload == {
        "status": "ok",
        "version": "0.1.0",
        "registered_agents": 1,
    }


def test_agent_query_routes_to_system_agent() -> None:
    with TestClient(app) as client:
        response = client.post("/api/agent/query", json={"query": "status"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
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


def test_request_id_header_is_preserved() -> None:
    with TestClient(app) as client:
        response = client.get("/health", headers={"X-Request-ID": "test-request-id"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-id"


def test_agent_metrics() -> None:
    with TestClient(app) as client:
        response = client.get("/api/agent/metrics")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "total_requests",
        "successful_requests",
        "failed_requests",
        "registered_agents",
    }
    assert payload["registered_agents"] == ["system"]
