"""SQLAlchemy ORM models for ego module (sessions, messages, records)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class EgoSession(Base):
    __tablename__ = "ego_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    role_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class EgoMessage(Base):
    __tablename__ = "ego_messages"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text, ForeignKey("ego_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    role_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_ego_messages_session_created", session_id, created_at),
    )


class EgoRecord(Base):
    __tablename__ = "ego_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'text'")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_date: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index("idx_ego_records_user_date", user_id, record_date.desc()),
    )
