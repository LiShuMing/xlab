"""Memory model for semantic search with pgvector.

This module defines the Memory ORM model which stores text content
with vector embeddings for semantic similarity search using PostgreSQL's
pgvector extension.
"""
from __future__ import annotations

from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, GUID


class Memory(Base):
    """Semantic memory stored with vector embeddings.

    Each memory represents a piece of information (from records or chat)
    stored with its vector embedding for semantic similarity search.

    Attributes:
        id: Primary key UUID.
        user_id: Foreign key to the user who owns this memory.
        content: The text content of the memory.
        embedding: Vector embedding (512-dim) for semantic search.
        source_type: Origin of the memory ('record' or 'chat').
        source_id: Optional reference to the source record.
        created_at: Timestamp when the memory was created.

    Example:
        memory = Memory(
            user_id=user.id,
            content="User felt happy today after walking in the park",
            embedding=[0.1, 0.2, ...],  # 512-dim vector
            source_type="record",
            source_id=record.id,
        )
    """

    __tablename__ = "memories"

    id: Mapped[UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    embedding: Mapped[list[float]] = Column(
        Vector(512),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="Source type: 'record' or 'chat'",
    )
    source_id: Mapped[UUID | None] = mapped_column(
        GUID(),
        ForeignKey("daily_records.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        """Return string representation of the memory."""
        return f"<Memory(id={self.id}, user_id={self.user_id}, source_type={self.source_type})>"
