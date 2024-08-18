"""Tests for AuthService and authentication dependencies."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.services.auth_service import AuthService
from app.models import User


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock()
    return redis_mock


@pytest.fixture
def mock_user():
    """Create a mock user instance."""
    user = User(id=uuid4(), openid="test-openid-123")
    user.nickname = "Test User"
    user.avatar_url = "https://example.com/avatar.png"
    return user


class TestAuthService:
    """Tests for AuthService class."""

    @pytest.mark.asyncio
    async def test_auth_service_init(self, mock_db, mock_redis):
        """Test AuthService initialization."""
        service = AuthService(mock_db, mock_redis)
        assert service._db == mock_db
        assert service._redis == mock_redis

    @pytest.mark.asyncio
    async def test_get_or_create_user_existing(self, mock_db, mock_redis, mock_user):
        """Test finding an existing user."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        service = AuthService(mock_db, mock_redis)

        with patch.object(
            service, "_get_wechat_session", new_callable=AsyncMock
        ) as mock_wechat:
            mock_wechat.return_value = {
                "openid": "test-openid-123",
                "session_key": "test-session-key",
            }

            user, access_token, refresh_token = await service.login_with_wechat(
                "test-code"
            )

            assert user.openid == "test-openid-123"
            assert access_token is not None
            assert refresh_token is not None

    @pytest.mark.asyncio
    async def test_get_wechat_session_success(self, mock_db, mock_redis):
        """Test successful WeChat session retrieval."""
        service = AuthService(mock_db, mock_redis)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "openid": "test-openid",
            "session_key": "test-session-key",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await service._get_wechat_session("test-code")

            assert result["openid"] == "test-openid"
            assert result["session_key"] == "test-session-key"

    @pytest.mark.asyncio
    async def test_get_wechat_session_error(self, mock_db, mock_redis):
        """Test WeChat session retrieval with error response."""
        from app.utils import WechatAuthException

        service = AuthService(mock_db, mock_redis)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "errcode": 40029,
            "errmsg": "invalid code",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            with pytest.raises(WechatAuthException) as exc_info:
                await service._get_wechat_session("invalid-code")

            assert "invalid code" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_refresh_access_token_valid(self, mock_db, mock_redis):
        """Test refreshing access token with valid refresh token."""
        from app.utils import verify_refresh_token

        user_id = str(uuid4())
        refresh_token = "valid-refresh-token"

        mock_redis.get = AsyncMock(return_value=refresh_token)

        service = AuthService(mock_db, mock_redis)

        with patch(
            "app.services.auth_service.verify_refresh_token"
        ) as mock_verify:
            mock_verify.return_value = {"sub": user_id}

            new_token = await service.refresh_access_token(refresh_token)

            assert new_token is not None
            mock_redis.get.assert_called_once_with(f"refresh_token:{user_id}")

    @pytest.mark.asyncio
    async def test_refresh_access_token_invalid(self, mock_db, mock_redis):
        """Test refreshing access token with invalid refresh token."""
        from app.utils import UnauthorizedException

        service = AuthService(mock_db, mock_redis)

        with patch(
            "app.services.auth_service.verify_refresh_token"
        ) as mock_verify:
            mock_verify.return_value = None

            with pytest.raises(UnauthorizedException):
                await service.refresh_access_token("invalid-token")

    @pytest.mark.asyncio
    async def test_refresh_access_token_not_stored(self, mock_db, mock_redis):
        """Test refreshing access token when token not in Redis."""
        from app.utils import UnauthorizedException

        user_id = str(uuid4())
        refresh_token = "valid-refresh-token"

        mock_redis.get = AsyncMock(return_value=None)

        service = AuthService(mock_db, mock_redis)

        with patch(
            "app.services.auth_service.verify_refresh_token"
        ) as mock_verify:
            mock_verify.return_value = {"sub": user_id}

            with pytest.raises(UnauthorizedException) as exc_info:
                await service.refresh_access_token(refresh_token)

            assert "not found or expired" in str(exc_info.value)