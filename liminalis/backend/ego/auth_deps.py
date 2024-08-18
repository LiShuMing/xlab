"""FastAPI dependency that extracts the ego user_id from a Bearer JWT."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend._shared.auth import decode_access_token
from backend.settings import Settings, get_settings

security = HTTPBearer(auto_error=False)


async def require_ego_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Bearer token"
        )
    payload = decode_access_token(settings, credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    return payload.user_id
