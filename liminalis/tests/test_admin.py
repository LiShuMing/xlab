"""Auth flow smoke tests for /api/admin."""

from fastapi.testclient import TestClient


def test_me_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/admin/me")
    assert response.status_code == 200
    assert response.json() == {"authenticated": False, "user": None}


def test_login_rejects_wrong_password(client: TestClient) -> None:
    response = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid credentials"}


def test_login_then_me_returns_user(client: TestClient) -> None:
    login = client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "test-password"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body == {"ok": True, "user": "admin"}

    set_cookie = login.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    # Default dev config: Secure should NOT be set so localhost http works.
    assert "Secure" not in set_cookie

    me = client.get("/api/admin/me")
    assert me.status_code == 200
    assert me.json() == {"authenticated": True, "user": "admin"}


def test_cookie_is_secure_when_flag_set(
    monkeypatch,
    client: TestClient,  # noqa: ANN001 — pytest fixture types
) -> None:
    monkeypatch.setenv("COOKIE_SECURE", "true")
    from backend.app import create_app
    from backend.settings import get_settings

    get_settings.cache_clear()
    secure_client = TestClient(create_app())
    response = secure_client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "test-password"},
    )
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]
