"""Tests for WeChat H5 OAuth wiring."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.services import wechat_service
from backend.settings import get_settings


def test_wechat_oauth_start_requires_configuration(client: TestClient) -> None:
    response = client.get("/api/wechat/official/oauth/start", follow_redirects=False)
    assert response.status_code == 503


def test_wechat_oauth_start_redirects_to_wechat(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_OFFICIAL_APP_ID", "wx_test_app")
    monkeypatch.setenv(
        "WECHAT_OFFICIAL_OAUTH_REDIRECT_URI",
        "https://example.com/api/wechat/official/oauth/callback",
    )
    get_settings.cache_clear()

    from backend.app import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get(
        "/api/wechat/official/oauth/start?target=/ego/chat",
        follow_redirects=False,
    )

    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith("https://open.weixin.qq.com/connect/oauth2/authorize?")
    assert "appid=wx_test_app" in location
    assert "scope=snsapi_base" in location
    assert "state=" in location


def test_wechat_official_tab_entry_redirects_to_wechat(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_OFFICIAL_APP_ID", "wx_test_app")
    monkeypatch.setenv(
        "WECHAT_OFFICIAL_OAUTH_REDIRECT_URI",
        "https://example.com/api/wechat/official/oauth/callback",
    )
    get_settings.cache_clear()

    from backend.app import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/api/wechat/official/entry/radar", follow_redirects=False)

    assert response.status_code == 307
    location = response.headers["location"]
    assert "appid=wx_test_app" in location
    state = location.split("state=", 1)[1].split("#", 1)[0]
    parsed = wechat_service.parse_oauth_state(get_settings(), state)
    assert parsed["target"] == "/radar"


def test_wechat_official_tab_entry_rejects_unknown_tab(client: TestClient) -> None:
    response = client.get("/api/wechat/official/entry/unknown", follow_redirects=False)
    assert response.status_code == 404


def test_wechat_oauth_callback_supports_mock_openid_without_postgres(monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_OFFICIAL_APP_ID", "wx_test_app")
    monkeypatch.setenv("WECHAT_OFFICIAL_MOCK_OPENID", "mock_openid_001")
    monkeypatch.delenv("PGSQL_HOST", raising=False)
    monkeypatch.delenv("PGSQL_URL", raising=False)
    monkeypatch.delenv("PGSQL_USER", raising=False)
    monkeypatch.delenv("PGSQL_PASSWORD", raising=False)
    get_settings.cache_clear()

    settings = get_settings()
    state = wechat_service.create_oauth_state(settings, target="/ego/chat")

    from backend.app import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get(
        f"/api/wechat/official/oauth/callback?code=mock-code&state={state}",
        follow_redirects=False,
    )

    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith("/wechat/callback#?")
    assert "account_label=wechat-id_001" in location
    assert "target=%2Fego%2Fchat" in location


def test_wechat_oauth_state_sanitizes_target() -> None:
    settings = get_settings()
    state = wechat_service.create_oauth_state(settings, target="//evil.example/path")
    parsed = wechat_service.parse_oauth_state(settings, state)
    assert parsed["target"] == "/ego/chat"


def test_wechat_tab_targets_cover_public_tabs() -> None:
    assert wechat_service.target_for_tab("code-lab") == "/codex"
    assert wechat_service.target_for_tab("blogs") == "/blogs"
    assert wechat_service.target_for_tab("database-radar") == "/radar"
    assert wechat_service.target_for_tab("value-invest") == "/invest"
    assert wechat_service.target_for_tab("ai-chat") == "/ai-chat"


def test_wechat_frontend_callback_url_contains_session_fields() -> None:
    result = wechat_service.WeChatLoginResult(
        token="token.value",
        user_id="user_123",
        account_label="wechat-abc123",
        target="/ego/chat",
    )
    url = wechat_service.build_frontend_callback_url(result)

    assert url.startswith("/wechat/callback#?")
    assert "token=token.value" in url
    assert "account_id=user_123" in url
    assert "account_label=wechat-abc123" in url
    assert "target=%2Fego%2Fchat" in url
