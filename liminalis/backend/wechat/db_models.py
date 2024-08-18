"""SQLAlchemy models for cross-provider user identity mapping."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class UserIdentity(Base):
    __tablename__ = "user_identities"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    app_id: Mapped[str] = mapped_column(Text, nullable=False)
    openid: Mapped[str] = mapped_column(Text, nullable=False)
    unionid: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("provider", "app_id", "openid", name="uq_user_identity_provider_app_openid"),
        Index("idx_user_identities_user_provider", "user_id", "provider"),
    )

