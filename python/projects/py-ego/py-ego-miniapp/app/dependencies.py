"""FastAPI dependencies for request handling.

This module provides dependency injection functions for:
- Database sessions
- Redis connections
- Authentication
"""

from typing import AsyncGenerator

import redis.asyncio as redis
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_maker
from app.models import User
from app.utils import UnauthorizedException, verify_access_token

settings = get_settings()
security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session.

    This is the primary dependency for database access in FastAPI endpoints.

    Yields:
        AsyncSession: SQLAlchemy async session for database operations.

    Example:
        ```python
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
        ```
    """
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> redis.Redis:
    """Provide a Redis client connection.

    Returns:
        redis.Redis: Async Redis client instance.

    Note:
        The caller is responsible for connection management.
        For most use cases, the connection pool handles this automatically.
    """
    return redis.from_url(settings.redis_url, decode_responses=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current authenticated user from JWT token.

    This dependency validates the Bearer token from the Authorization header
    and retrieves the corresponding user from the database.

    Args:
        credentials: HTTP Bearer credentials from the request header.
        db: Async database session.

    Returns:
        User: The authenticated user model instance.

    Raises:
        UnauthorizedException: If the token is invalid, expired, or user not found.

    Example:
        ```python
        @app.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return {"id": str(user.id), "nickname": user.nickname}
        ```
    """
    token = credentials.credentials
    payload = verify_access_token(token)

    if not payload:
        raise UnauthorizedException("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise UnauthorizedException("User not found")

    if not user.is_active:
        raise UnauthorizedException("User is inactive")

    return user