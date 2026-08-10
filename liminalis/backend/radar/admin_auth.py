"""Legacy-compatible admin authentication helpers for Radar.

FastAPI routes use ``backend.services.radar_admin_service``. This module keeps
the old function names without importing Flask.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from werkzeug.security import check_password_hash

from backend.settings import get_settings as get_runtime_settings

F = TypeVar("F", bound=Callable)


def admin_username() -> str:
    return get_runtime_settings().radar_admin_user


def verify_admin_password(password: str) -> bool:
    settings = get_runtime_settings()
    password_hash = settings.radar_admin_password_hash or ""
    plain_password = settings.radar_admin_password

    if password_hash:
        return check_password_hash(password_hash, password)

    # Local-development fallback. Production should set RADAR_ADMIN_PASSWORD_HASH.
    return bool(plain_password) and password == plain_password


def is_admin_authenticated(session_data: dict[str, Any] | None = None) -> bool:
    return bool(session_data) and session_data.get("radar_admin") == admin_username()


def login_admin(session_data: dict[str, Any]) -> None:
    session_data["radar_admin"] = admin_username()


def logout_admin(session_data: dict[str, Any]) -> None:
    session_data.pop("radar_admin", None)


def require_admin(fn: F) -> F:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_admin_authenticated():
            return {"error": "admin authentication required"}, 401
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
