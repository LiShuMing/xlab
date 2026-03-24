"""Tests for chat API endpoints.

This module tests the chat API endpoints including:
- Session creation and management
- Message sending and retrieval
- Authentication requirements
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_sessions_unauthorized():
    """Test that listing chat sessions requires authentication."""
    response = client.get("/api/chat/sessions")
    assert response.status_code == 401


def test_create_session_unauthorized():
    """Test that creating a session requires authentication."""
    response = client.post("/api/chat/sessions", json={"role_id": "therapist"})
    assert response.status_code == 401


def test_send_message_unauthorized():
    """Test that sending a message requires authentication."""
    response = client.post(
        "/api/chat/sessions/00000000-0000-0000-0000-000000000000/messages",
        json={"content": "Hello"},
    )
    assert response.status_code == 401


def test_list_messages_unauthorized():
    """Test that listing messages requires authentication."""
    response = client.get(
        "/api/chat/sessions/00000000-0000-0000-0000-000000000000/messages"
    )
    assert response.status_code == 401


def test_delete_session_unauthorized():
    """Test that deleting a session requires authentication."""
    response = client.delete("/api/chat/sessions/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 401


def test_update_session_unauthorized():
    """Test that updating a session requires authentication."""
    response = client.patch(
        "/api/chat/sessions/00000000-0000-0000-0000-000000000000?action=end"
    )
    assert response.status_code == 401