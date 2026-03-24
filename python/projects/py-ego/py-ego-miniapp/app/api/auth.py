"""Authentication API routes for WeChat mini program.

This module provides endpoints for:
- WeChat login (code exchange for JWT tokens)
- Token refresh
"""

from fastapi import APIRouter, Depends, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis
from app.schemas import (
    ErrorResponse,
    LoginRequest,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}},
    summary="Login with WeChat code",
    description="Exchange WeChat login code for JWT tokens and user info",
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> TokenResponse:
    """Login with WeChat authorization code.

    This endpoint exchanges a WeChat login code for JWT tokens.
    The code is obtained from wx.login() in the WeChat mini program.

    Args:
        request: Login request containing the WeChat authorization code.
        db: Async database session.
        redis_client: Redis client for token storage.

    Returns:
        TokenResponse: Contains access token, refresh token, and user info.

    Raises:
        WechatAuthException: If WeChat authentication fails.
    """
    service = AuthService(db, redis_client)
    user, access_token, refresh_token = await service.login_with_wechat(request.code)

    return TokenResponse(
        token=access_token,
        refresh_token=refresh_token,
        user=user,
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    status_code=status.HTTP_200_OK,
    responses={401: {"model": ErrorResponse}},
    summary="Refresh access token",
    description="Get a new access token using a valid refresh token",
)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> RefreshResponse:
    """Refresh access token using a valid refresh token.

    This endpoint generates a new access token when the current one expires.
    The refresh token must be valid and stored in Redis.

    Args:
        request: Refresh request containing the refresh token.
        db: Async database session.
        redis_client: Redis client for token validation.

    Returns:
        RefreshResponse: Contains a new access token.

    Raises:
        UnauthorizedException: If the refresh token is invalid or expired.
    """
    service = AuthService(db, redis_client)
    new_token = await service.refresh_access_token(request.refresh_token)

    return RefreshResponse(token=new_token)