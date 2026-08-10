"""JWT authentication primitives.

M0 ships only the encode/decode primitives that M3 (py-ego absorption) will
use. The current admin cookie flow in routers/admin.py keeps working until
M3 swaps it out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeSerializer, URLSafeTimedSerializer
from jose import JWTError, jwt
from passlib.context import CryptContext

from backend._shared.serializers import utc_now
from backend.settings import Settings

DEFAULT_ALGORITHM = "HS256"
DEFAULT_ACCESS_TTL = timedelta(hours=12)

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(frozen=True)
class TokenPayload:
    """The subset of JWT claims that matter to liminalis."""

    user_id: str
    role: str
    expires_at: datetime


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


def issue_access_token(
    settings: Settings,
    *,
    user_id: str,
    role: str = "user",
    ttl: timedelta = DEFAULT_ACCESS_TTL,
) -> str:
    now = utc_now()
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.session_secret, algorithm=DEFAULT_ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> TokenPayload | None:
    try:
        claims = jwt.decode(token, settings.session_secret, algorithms=[DEFAULT_ALGORITHM])
    except JWTError:
        return None
    return TokenPayload(
        user_id=str(claims.get("sub", "")),
        role=str(claims.get("role", "user")),
        expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
    )


def sign_payload(settings: Settings, payload: dict[str, Any], *, salt: str) -> str:
    """Sign a small cookie/session payload."""
    return URLSafeSerializer(settings.session_secret, salt=salt).dumps(payload)


def read_signed_payload(settings: Settings, token: str | None, *, salt: str) -> dict[str, Any] | None:
    """Read a signed payload, returning ``None`` for invalid or missing tokens."""
    if not token:
        return None
    try:
        payload = URLSafeSerializer(settings.session_secret, salt=salt).loads(token)
    except BadSignature:
        return None
    return payload if isinstance(payload, dict) else None


class SignedStateError(ValueError):
    """Raised when a timed signed state token is invalid or expired."""


def sign_timed_payload(settings: Settings, payload: dict[str, Any], *, salt: str) -> str:
    """Sign a timed state payload."""
    return URLSafeTimedSerializer(settings.session_secret, salt=salt).dumps(payload)


def read_timed_payload(
    settings: Settings,
    token: str,
    *,
    salt: str,
    max_age_seconds: int,
) -> dict[str, Any]:
    """Read a timed state payload and raise a shared error on failure."""
    try:
        payload = URLSafeTimedSerializer(settings.session_secret, salt=salt).loads(
            token,
            max_age=max_age_seconds,
        )
    except SignatureExpired as exc:
        raise SignedStateError("signed state expired") from exc
    except BadSignature as exc:
        raise SignedStateError("invalid signed state") from exc
    if not isinstance(payload, dict):
        raise SignedStateError("invalid signed state")
    return payload
