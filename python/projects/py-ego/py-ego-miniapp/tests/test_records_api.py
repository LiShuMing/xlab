"""Tests for Record API endpoints."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestRecordsAPIUnauthorized:
    """Tests for record API endpoints without authentication."""

    def test_list_records_unauthorized(self) -> None:
        """Test that listing records requires authentication."""
        response = client.get("/api/records")
        assert response.status_code == 403

    def test_create_record_unauthorized(self) -> None:
        """Test that creating records requires authentication."""
        response = client.post(
            "/api/records",
            json={"content_type": "text", "content": "test content"},
        )
        assert response.status_code == 403

    def test_get_record_unauthorized(self) -> None:
        """Test that getting a record requires authentication."""
        response = client.get("/api/records/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 403

    def test_delete_record_unauthorized(self) -> None:
        """Test that deleting a record requires authentication."""
        response = client.delete("/api/records/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 403

    def test_timeline_unauthorized(self) -> None:
        """Test that timeline requires authentication."""
        response = client.get("/api/records/timeline?month=2026-03")
        assert response.status_code == 403


class TestRecordsAPIRoutes:
    """Tests for record API routes registration."""

    def test_records_routes_in_openapi(self) -> None:
        """Test that records routes are included in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        # Check that records routes are included
        assert "/api/records" in data["paths"]
        assert "/api/records/{record_id}" in data["paths"]
        assert "/api/records/timeline" in data["paths"]

    def test_records_route_methods(self) -> None:
        """Test that records routes have correct HTTP methods."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        paths = data["paths"]

        # Check /api/records methods
        assert "post" in paths["/api/records"]
        assert "get" in paths["/api/records"]

        # Check /api/records/{record_id} methods
        assert "get" in paths["/api/records/{record_id}"]
        assert "delete" in paths["/api/records/{record_id}"]

        # Check /api/records/timeline methods
        assert "get" in paths["/api/records/timeline"]