"""Settings validation tests — production env must reject placeholder secrets."""

import pytest
from pydantic import ValidationError


def test_dev_defaults_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    from backend.settings import Settings, get_settings

    get_settings.cache_clear()
    settings = Settings()
    assert settings.is_production is False
    assert settings.cors_allowed_origins == []


def test_production_rejects_default_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("RADAR_ADMIN_PASSWORD", "real-secret")
    # session_secret left as the dev default.

    from backend.settings import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "session_secret" in str(exc.value)


def test_production_rejects_default_admin_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.delenv("RADAR_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("RADAR_ADMIN_PASSWORD_HASH", raising=False)

    from backend.settings import Settings, get_settings

    get_settings.cache_clear()
    with pytest.raises(ValidationError) as exc:
        Settings()
    assert "radar_admin_password" in str(exc.value)


def test_production_passes_with_real_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SESSION_SECRET", "x" * 40)
    monkeypatch.setenv("RADAR_ADMIN_PASSWORD", "real-secret")

    from backend.settings import Settings, get_settings

    get_settings.cache_clear()
    settings = Settings()
    assert settings.is_production is True
    assert len(settings.session_secret) >= 32
