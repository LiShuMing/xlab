"""Chat session and message models."""

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, GUID


class ChatSession(Base):
    """Chat session model for grouping chat messages.

    Each session represents a conversation between a user and an AI role.
    Sessions can be ended and archived for history purposes.

    Attributes:
        id: UUID primary key.
        user_id: Reference to the User who owns this session.
        role_id: The AI role being used in this session (e.g., 'therapist').
        started_at: When the session was created.
        ended_at: When the session was ended (None if active).

    Relationships:
        user: Reference back to the User model.
        messages: One-to-many relationship with ChatMessage.
    """

    __tablename__ = "chat_sessions"

    id = Column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id = Column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id = Column(
        String(50),
        default="therapist",
    )
    started_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "ChatMessage",
        back_populates="session",
        lazy="dynamic",
    )


class ChatMessage(Base):
    """Chat message model for individual messages in a session.

    Stores each message exchanged between the user and AI assistant.

    Attributes:
        id: UUID primary key.
        session_id: Reference to the ChatSession this message belongs to.
        role: Who sent the message - 'user' or 'assistant'.
        content: The text content of the message.
        created_at: When the message was created.

    Relationships:
        session: Reference back to the ChatSession model.
    """

    __tablename__ = "chat_messages"

    id = Column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id = Column(
        GUID(),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(
        String(10),
        nullable=False,
    )  # 'user' or 'assistant'
    content = Column(
        Text,
        nullable=False,
    )
    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    session = relationship("ChatSession", back_populates="messages")