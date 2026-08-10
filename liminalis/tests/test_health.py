"""Smoke tests for /health."""

from fastapi.testclient import TestClient


def test_health_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "service" in body
    assert body["database"]["backend"] in {"postgres", "supabase_postgres", "unconfigured"}
    assert body["storage"]["business"]["class"] == "business_database"
    assert body["storage"]["runtimeCache"]["class"] == "runtime_cache"
    assert body["storage"]["staticSnapshot"]["class"] == "static_snapshot"


def test_deep_health_exposes_runtime_checks(client: TestClient) -> None:
    response = client.get("/health/deep")
    assert response.status_code in {200, 503}
    body = response.json()
    assert "checks" in body
    assert "database" in body["checks"]
    assert "llm" in body["checks"]
    assert "llmWiki" in body["checks"]
