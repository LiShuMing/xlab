"""SQLAlchemy ORM models for ego module (sessions, messages, records)."""

from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy import text as sa_text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class EgoSession(Base):
    __tablename__ = "ego_sessions"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    role_id: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))


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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))

    __table_args__ = (Index("idx_ego_messages_session_created", session_id, created_at),)


class EgoRecord(Base):
    __tablename__ = "ego_records"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(Text, nullable=False, server_default=sa_text("'text'"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_date: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))

    __table_args__ = (Index("idx_ego_records_user_date", user_id, record_date.desc()),)


class EgoMemory(Base):
    __tablename__ = "ego_memories"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    role_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sa_text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))

    __table_args__ = (
        Index("idx_ego_memories_user_role_created", user_id, role_id, created_at.desc()),
    )


class EgoProfile(Base):
    __tablename__ = "ego_profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    role_id: Mapped[str] = mapped_column(Text, nullable=False, server_default=sa_text("'global'"))
    content: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sa_text("now()"))

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_ego_profiles_user_role"),
        Index("idx_ego_profiles_user_role", user_id, role_id),
    )
