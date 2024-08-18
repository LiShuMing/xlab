"""Authentication API routes for WeChat mini program.

This module provides endpoints for:
- WeChat login (code exchange for JWT tokens)
- Token refresh
"""

from fastapi import APIRouter, Depends, Request, status
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_redis
from app.schemas import (
    ErrorResponse,
    LoginRequest,
    PinLoginRequest,
    RefreshRequest,
    RefreshResponse,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


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
    "/pin-login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={422: {"model": ErrorResponse}},
    summary="Login with 6-digit PIN",
    description="Use client IP plus a 6-digit PIN as the account identity.",
)
async def pin_login(
    request: PinLoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> TokenResponse:
    """Login with a six digit PIN scoped by client IP.

    Args:
        request: PIN login request.
        http_request: Raw HTTP request used to resolve client IP.
        db: Async database session.
        redis_client: Redis client for refresh token storage.

    Returns:
        TokenResponse: Access token, refresh token, and user info.
    """
    service = AuthService(db, redis_client)
    user, access_token, refresh_token = await service.login_with_pin(
        request.pin,
        _client_ip(http_request),
    )

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
