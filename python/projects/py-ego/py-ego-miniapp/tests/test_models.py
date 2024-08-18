"""Tests for SQLAlchemy model imports and basic structure."""

import pytest


def test_models_import():
    """Test that all models can be imported successfully."""
    from app.models import (
        Base,
        ChatMessage,
        ChatSession,
        DailyRecord,
        TimestampMixin,
        User,
        UserProfile,
        WechatSession,
    )

    assert Base is not None
    assert TimestampMixin is not None
    assert User is not None
    assert WechatSession is not None
    assert DailyRecord is not None
    assert UserProfile is not None
    assert ChatSession is not None
    assert ChatMessage is not None


def test_user_model_structure():
    """Test User model has expected attributes."""
    from app.models import User

    # Check table name
    assert User.__tablename__ == "users"

    # Check columns exist
    assert hasattr(User, "id")
    assert hasattr(User, "openid")
    assert hasattr(User, "nickname")
    assert hasattr(User, "avatar_url")
    assert hasattr(User, "last_active_at")
    assert hasattr(User, "deleted_at")
    assert hasattr(User, "created_at")
    assert hasattr(User, "updated_at")

    # Check properties
    assert hasattr(User, "is_active")


def test_daily_record_model_structure():
    """Test DailyRecord model has expected attributes."""
    from app.models import DailyRecord

    assert DailyRecord.__tablename__ == "daily_records"
    assert hasattr(DailyRecord, "id")
    assert hasattr(DailyRecord, "user_id")
    assert hasattr(DailyRecord, "content_type")
    assert hasattr(DailyRecord, "content")
    assert hasattr(DailyRecord, "media_url")
    assert hasattr(DailyRecord, "record_date")


def test_user_profile_model_structure():
    """Test UserProfile model has expected attributes."""
    from app.models import UserProfile

    assert UserProfile.__tablename__ == "user_profiles"
    assert hasattr(UserProfile, "id")
    assert hasattr(UserProfile, "user_id")
    assert hasattr(UserProfile, "role_id")
    assert hasattr(UserProfile, "global_profile")
    assert hasattr(UserProfile, "role_profiles")


def test_chat_session_model_structure():
    """Test ChatSession model has expected attributes."""
    from app.models import ChatSession

    assert ChatSession.__tablename__ == "chat_sessions"
    assert hasattr(ChatSession, "id")
    assert hasattr(ChatSession, "user_id")
    assert hasattr(ChatSession, "role_id")
    assert hasattr(ChatSession, "started_at")
    assert hasattr(ChatSession, "ended_at")


def test_chat_message_model_structure():
    """Test ChatMessage model has expected attributes."""
    from app.models import ChatMessage

    assert ChatMessage.__tablename__ == "chat_messages"
    assert hasattr(ChatMessage, "id")
    assert hasattr(ChatMessage, "session_id")
    assert hasattr(ChatMessage, "role")
    assert hasattr(ChatMessage, "content")
    assert hasattr(ChatMessage, "created_at")


@pytest.mark.asyncio
async def test_create_tables(db_engine):
    """Test that all tables can be created successfully."""
    from sqlalchemy import text

    async with db_engine.connect() as conn:
        # Check users table exists
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        )
        assert result.fetchone() is not None

        # Check daily_records table exists
        result = await conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='daily_records'"
            )
        )
        assert result.fetchone() is not None

        # Check user_profiles table exists
        result = await conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_profiles'"
            )
        )
        assert result.fetchone() is not None

        # Check chat_sessions table exists
        result = await conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_sessions'"
            )
        )
        assert result.fetchone() is not None

        # Check chat_messages table exists
        result = await conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chat_messages'"
            )
        )
        assert result.fetchone() is not None

        # Check wechat_sessions table exists
        result = await conn.execute(
            text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='wechat_sessions'"
            )
        )
        assert result.fetchone() is not None