"""Small session-based admin authentication for DB Radar APIs."""

from __future__ import annotations

import os
from functools import wraps
from typing import Callable, TypeVar

from flask import jsonify, session
from werkzeug.security import check_password_hash

F = TypeVar("F", bound=Callable)


def admin_username() -> str:
    return os.environ.get("RADAR_ADMIN_USER", "admin")


def verify_admin_password(password: str) -> bool:
    password_hash = os.environ.get("RADAR_ADMIN_PASSWORD_HASH", "")
    plain_password = os.environ.get("RADAR_ADMIN_PASSWORD", "")

    if password_hash:
        return check_password_hash(password_hash, password)

    # Local-development fallback. Production should set RADAR_ADMIN_PASSWORD_HASH.
    return bool(plain_password) and password == plain_password


def is_admin_authenticated() -> bool:
    return session.get("radar_admin") == admin_username()


def login_admin() -> None:
    session["radar_admin"] = admin_username()


def logout_admin() -> None:
    session.pop("radar_admin", None)


def require_admin(fn: F) -> F:
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not is_admin_authenticated():
            return jsonify({"error": "admin authentication required"}), 401
        return fn(*args, **kwargs)

    return wrapper  # type: ignore[return-value]
