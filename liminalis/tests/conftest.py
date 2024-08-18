"""Shared pytest fixtures for the liminalis backend test suite."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_settings_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    # Pin a known dev configuration so tests aren't sensitive to a stray
    # ~/.env / .env.local on the developer's machine.
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("RADAR_ADMIN_USER", "admin")
    monkeypatch.setenv("RADAR_ADMIN_PASSWORD", "test-password")
    monkeypatch.delenv("RADAR_ADMIN_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("COOKIE_SECURE", raising=False)

    from backend.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    from backend.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)
