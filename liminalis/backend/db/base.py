"""Declarative base shared by all liminalis SQLAlchemy models."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for ORM-mapped tables."""
