"""SQLAlchemy declarative base and common mixins."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent GUID type that stores UUID as string in SQLite.

    Uses PostgreSQL's native UUID type when available,
    otherwise stores as 36-character string.

    This allows the same model to work with both:
    - PostgreSQL (production) - native UUID type
    - SQLite (testing) - string type
    """

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        """Load the appropriate implementation based on dialect.

        Args:
            dialect: The database dialect in use.

        Returns:
            The appropriate column type for the dialect.
        """
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        """Process the value before binding to the database.

        Args:
            value: The value to process.
            dialect: The database dialect in use.

        Returns:
            The processed value suitable for storage.
        """
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if isinstance(value, uuid.UUID):
            return str(value)
        return value


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp columns.

    These columns are automatically managed by SQLAlchemy.
    """

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )