"""Tests for JWT handler and exception classes."""

from app.utils import (
    NotFoundException,
    RateLimitException,
    UnauthorizedException,
    ValidationException,
    WechatAuthException,
)
from app.utils.jwt_handler import create_access_token, create_refresh_token, verify_access_token, verify_refresh_token


def test_create_and_verify_access_token():
    """Test creating and verifying an access token."""
    data = {"sub": "user-123"}
    token = create_access_token(data)
    assert token is not None
    assert isinstance(token, str)

    payload = verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "access"


def test_create_and_verify_refresh_token():
    """Test creating and verifying a refresh token."""
    data = {"sub": "user-123"}
    token = create_refresh_token(data)
    assert token is not None
    assert isinstance(token, str)

    payload = verify_refresh_token(token)
    assert payload is not None
    assert payload["sub"] == "user-123"
    assert payload["type"] == "refresh"


def test_verify_wrong_token_type():
    """Test that access token is not verified as refresh token."""
    data = {"sub": "user-123"}
    token = create_access_token(data)

    # Access token should not verify as refresh
    payload = verify_refresh_token(token)
    assert payload is None


def test_invalid_token_returns_none():
    """Test that invalid tokens return None."""
    payload = verify_access_token("invalid-token")
    assert payload is None


def test_exception_hierarchy():
    """Test exception classes and their attributes."""
    exc = UnauthorizedException("test")
    assert exc.code == "UNAUTHORIZED"
    assert exc.message == "test"
    assert exc.status_code == 401

    exc = NotFoundException("not here")
    assert exc.code == "NOT_FOUND"
    assert exc.status_code == 404

    exc = ValidationException("invalid data")
    assert exc.code == "VALIDATION_ERROR"
    assert exc.status_code == 422

    exc = WechatAuthException("wechat error")
    assert exc.code == "WECHAT_AUTH_FAILED"
    assert exc.status_code == 401

    exc = RateLimitException("slow down")
    assert exc.code == "RATE_LIMITED"
    assert exc.status_code == 429