"""Authentication service for WeChat mini program login.

This module provides the AuthService class that handles:
- WeChat code-to-session exchange
- User creation and retrieval
- JWT token generation and refresh
- Session key storage
"""

from datetime import datetime, timedelta, timezone

import httpx
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import User, UserProfile, WechatSession
from app.utils import (
    UnauthorizedException,
    WechatAuthException,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)

settings = get_settings()


class AuthService:
    """Service handling WeChat mini program authentication.

    This service manages the complete authentication flow:
    1. Exchange WeChat code for session info (openid, session_key)
    2. Find or create user based on openid
    3. Generate and manage JWT tokens
    4. Store WeChat session key for later use (decryption)

    Attributes:
        _db: SQLAlchemy async session for database operations.
        _redis: Redis client for token storage.
    """

    def __init__(self, db: AsyncSession, redis_client: redis.Redis):
        """Initialize the authentication service.

        Args:
            db: SQLAlchemy async session for database operations.
            redis_client: Redis client for storing refresh tokens.
        """
        self._db = db
        self._redis = redis_client

    async def login_with_wechat(self, code: str) -> tuple[User, str, str]:
        """Exchange WeChat authorization code for user tokens.

        This is the main entry point for WeChat login. It:
        1. Calls WeChat's jscode2session API with the provided code
        2. Gets or creates a user based on the returned openid
        3. Stores the session_key for later use
        4. Generates access and refresh tokens

        Args:
            code: Authorization code from WeChat login (wx.login).

        Returns:
            tuple[User, str, str]: A tuple containing:
                - User: The user model instance (existing or newly created)
                - str: JWT access token
                - str: JWT refresh token

        Raises:
            WechatAuthException: If WeChat API returns an error.
        """
        wechat_data = await self._get_wechat_session(code)

        openid = wechat_data.get("openid")
        session_key = wechat_data.get("session_key")

        if not openid:
            raise WechatAuthException("Failed to get openid from WeChat")

        user = await self._get_or_create_user(openid)
        await self._store_wechat_session(user.id, session_key)

        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        await self._redis.setex(
            f"refresh_token:{user.id}",
            settings.jwt_refresh_token_expire_days * 24 * 60 * 60,
            refresh_token,
        )

        return user, access_token, refresh_token

    async def _get_wechat_session(self, code: str) -> dict:
        """Call WeChat's jscode2session API to exchange code for session info.

        Args:
            code: Authorization code from WeChat login.

        Returns:
            dict: WeChat session data containing:
                - openid: Unique user identifier for the mini program
                - session_key: Key for decrypting user data
                - unionid: Optional unique identifier across WeChat apps

        Raises:
            WechatAuthException: If the API call fails or returns an error.
        """
        url = "https://api.weixin.qq.com/sns/jscode2session"
        params = {
            "appid": settings.wechat_app_id,
            "secret": settings.wechat_app_secret,
            "js_code": code,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            data = response.json()

        if "errcode" in data and data["errcode"] != 0:
            raise WechatAuthException(
                f"WeChat error: {data.get('errmsg', 'Unknown error')}"
            )

        return data

    async def _get_or_create_user(self, openid: str) -> User:
        """Find an existing user or create a new one.

        Args:
            openid: WeChat user identifier.

        Returns:
            User: The existing or newly created user model instance.
        """
        result = await self._db.execute(select(User).where(User.openid == openid))
        user = result.scalar_one_or_none()

        if user:
            return user

        user = User(openid=openid)
        self._db.add(user)
        await self._db.flush()

        profile = UserProfile(user_id=user.id)
        self._db.add(profile)

        await self._db.commit()
        await self._db.refresh(user)

        return user

    async def _store_wechat_session(self, user_id: str, session_key: str) -> None:
        """Store WeChat session key for later use.

        The session key is needed for decrypting user data like
        phone numbers and other sensitive information.

        Args:
            user_id: UUID of the user.
            session_key: WeChat session key.
        """
        wechat_session = WechatSession(
            user_id=user_id,
            session_key=session_key,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        self._db.add(wechat_session)
        await self._db.commit()

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Generate a new access token from a refresh token.

        Args:
            refresh_token: Valid JWT refresh token.

        Returns:
            str: New JWT access token.

        Raises:
            UnauthorizedException: If the refresh token is invalid or expired.
        """
        payload = verify_refresh_token(refresh_token)
        if not payload:
            raise UnauthorizedException("Invalid refresh token")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedException("Invalid token payload")

        stored_token = await self._redis.get(f"refresh_token:{user_id}")
        if stored_token != refresh_token:
            raise UnauthorizedException("Refresh token not found or expired")

        return create_access_token({"sub": user_id})