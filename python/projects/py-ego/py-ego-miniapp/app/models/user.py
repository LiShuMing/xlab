"""User and WeChat session models."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import relationship

from app.models.base import Base, GUID, TimestampMixin


class User(Base, TimestampMixin):
    """User model representing a WeChat mini program user.

    Attributes:
        id: UUID primary key.
        openid: WeChat unique user identifier.
        nickname: User's display name.
        avatar_url: URL to user's avatar image.
        current_role_id: The user's preferred AI role (default: 'therapist').
        last_active_at: Timestamp of last user activity.
        deleted_at: Soft delete timestamp (None if active).

    Relationships:
        profile: One-to-one relationship with UserProfile.
        records: One-to-many relationship with DailyRecord.
        chat_sessions: One-to-many relationship with ChatSession.
    """

    __tablename__ = "users"

    id = Column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    openid = Column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    nickname = Column(String(100))
    avatar_url = Column(String(500))
    current_role_id = Column(
        String(50),
        default="therapist",
        nullable=False,
    )
    last_active_at = Column(DateTime)
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    profile = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        lazy="selectin",
    )
    records = relationship(
        "DailyRecord",
        back_populates="user",
        lazy="dynamic",
    )
    chat_sessions = relationship(
        "ChatSession",
        back_populates="user",
        lazy="dynamic",
    )

    @property
    def is_active(self) -> bool:
        """Check if the user account is active.

        Returns:
            bool: True if user is not soft-deleted, False otherwise.
        """
        return self.deleted_at is None


class WechatSession(Base):
    """WeChat session model for storing user session keys.

    This model stores the session_key received from WeChat login,
    which is needed for decrypting user data.

    Attributes:
        id: UUID primary key.
        user_id: Reference to the User.
        session_key: WeChat session key for data decryption.
        expires_at: Session expiration timestamp.
        created_at: Session creation timestamp.
    """

    __tablename__ = "wechat_sessions"

    id = Column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id = Column(
        GUID(),
        nullable=False,
        index=True,
    )
    session_key = Column(
        String(100),
        nullable=False,
    )
    expires_at = Column(
        DateTime,
        nullable=False,
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )