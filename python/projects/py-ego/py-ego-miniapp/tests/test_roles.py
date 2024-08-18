"""Tests for Role API endpoints.

This module tests the role API endpoints including:
- Listing all available roles
- Getting detailed information about specific roles
- Error handling for invalid role IDs
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestRolesAPI:
    """Tests for role API endpoints."""

    def test_list_roles(self) -> None:
        """Test listing all available roles."""
        response = client.get("/api/roles")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 4  # therapist, researcher, learner, philosopher

        # Check that all expected roles are present
        role_ids = {role["id"] for role in data}
        expected_ids = {"therapist", "researcher", "learner", "philosopher"}
        assert role_ids == expected_ids

        # Check structure of each role
        for role in data:
            assert "id" in role
            assert "name" in role
            assert "icon" in role
            assert "description" in role
            # Should NOT have detailed fields
            assert "system_prompt" not in role
            assert "personality" not in role
            assert "knowledge" not in role

    def test_get_role_detail_therapist(self) -> None:
        """Test getting detailed information about the therapist role."""
        response = client.get("/api/roles/therapist")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == "therapist"
        assert data["name"] == "心理陪护师"
        assert data["icon"] == "🧠"
        assert "description" in data
        assert "system_prompt" in data
        assert "personality" in data
        assert "knowledge" in data
        assert "examples" in data

        # Check personality structure
        personality = data["personality"]
        assert "background" in personality
        assert "traits" in personality
        assert "speaking_style" in personality
        assert "catchphrases" in personality

        # Check knowledge structure
        knowledge = data["knowledge"]
        assert "domain_expertise" in knowledge
        assert "key_concepts" in knowledge
        assert "classic_quotes" in knowledge
        assert "references" in knowledge

    def test_get_role_detail_researcher(self) -> None:
        """Test getting detailed information about the researcher role."""
        response = client.get("/api/roles/researcher")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == "researcher"
        assert data["name"] == "研究员"
        assert data["icon"] == "🔬"

    def test_get_role_detail_learner(self) -> None:
        """Test getting detailed information about the learner role."""
        response = client.get("/api/roles/learner")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == "learner"
        assert data["name"] == "学习者"
        assert data["icon"] == "📚"

    def test_get_role_detail_philosopher(self) -> None:
        """Test getting detailed information about the philosopher role."""
        response = client.get("/api/roles/philosopher")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == "philosopher"
        assert data["name"] == "哲学家"
        assert data["icon"] == "🤔"

    def test_get_role_detail_not_found(self) -> None:
        """Test getting details for a non-existent role returns 404."""
        response = client.get("/api/roles/nonexistent")
        assert response.status_code == 404

        data = response.json()
        assert "detail" in data
        assert "nonexistent" in data["detail"]


class TestRolesAPIRoutes:
    """Tests for role API routes registration."""

    def test_roles_routes_in_openapi(self) -> None:
        """Test that roles routes are included in OpenAPI schema."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "paths" in data
        # Check that roles routes are included
        assert "/api/roles" in data["paths"]
        assert "/api/roles/{role_id}" in data["paths"]

    def test_roles_route_methods(self) -> None:
        """Test that roles routes have correct HTTP methods."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        paths = data["paths"]

        # Check /api/roles methods (list)
        assert "get" in paths["/api/roles"]

        # Check /api/roles/{role_id} methods (detail)
        assert "get" in paths["/api/roles/{role_id}"]
