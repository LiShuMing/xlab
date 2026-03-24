"""Tests for the FastAPI application entry point."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check() -> None:
    """Test health check endpoint returns ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "env" in data


def test_root() -> None:
    """Test root endpoint returns API info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["name"] == "py-ego-miniapp"
    assert "version" in data
    assert "docs" in data


def test_docs_available() -> None:
    """Test OpenAPI docs endpoint is accessible."""
    response = client.get("/docs")
    assert response.status_code == 200


def test_redoc_available() -> None:
    """Test ReDoc endpoint is accessible."""
    response = client.get("/redoc")
    assert response.status_code == 200


def test_openapi_json_available() -> None:
    """Test OpenAPI JSON schema is available."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert "openapi" in data
    assert "paths" in data
    # Check that auth routes are included
    assert "/api/auth/login" in data["paths"]
    assert "/api/auth/refresh" in data["paths"]