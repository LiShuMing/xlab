"""Smoke tests for /health."""

from fastapi.testclient import TestClient


def test_health_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "service" in body
    assert body["database"]["backend"] in {"postgres", "fallback"}
