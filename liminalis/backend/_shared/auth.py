"""JWT authentication primitives.

M0 ships only the encode/decode primitives that M3 (py-ego absorption) will
use. The current admin cookie flow in routers/admin.py keeps working until
M3 swaps it out.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

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
    now = datetime.now(UTC)
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
