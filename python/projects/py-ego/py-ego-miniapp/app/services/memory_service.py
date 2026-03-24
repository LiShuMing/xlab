"""Memory service for semantic search operations.

This module provides the MemoryService class for managing memories
with pgvector-based semantic similarity search.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import get_embedding
from app.models import Memory, User


class MemoryService:
    """Service for memory operations with pgvector.

    This service provides methods to add memories, search by semantic
    similarity, and manage memory records for users.

    Attributes:
        _db: Async SQLAlchemy session for database operations.
        _user: The authenticated user whose memories are being managed.

    Example:
        service = MemoryService(db, current_user)
        memory = await service.add_memory(
            content="User had a great day at work",
            source_type="record",
        )
        similar = await service.search_memories("work happiness", k=3)
    """

    def __init__(self, db: AsyncSession, user: User):
        """Initialize the memory service.

        Args:
            db: Async database session.
            user: The authenticated user.
        """
        self._db = db
        self._user = user

    async def add_memory(
        self,
        content: str,
        source_type: str,
        source_id: UUID | None = None,
    ) -> Memory:
        """Add a new memory with embedding.

        Generates an embedding for the content and stores it in the database.

        Args:
            content: The text content of the memory.
            source_type: Origin of the memory ('record' or 'chat').
            source_id: Optional reference to the source record.

        Returns:
            Memory: The created memory instance.
        """
        embedding = await get_embedding(content)

        memory = Memory(
            user_id=self._user.id,
            content=content,
            embedding=embedding.tolist(),
            source_type=source_type,
            source_id=source_id,
        )
        self._db.add(memory)
        await self._db.commit()
        await self._db.refresh(memory)
        return memory

    async def search_memories(
        self,
        query: str,
        k: int = 5,
    ) -> list[Memory]:
        """Search memories by semantic similarity.

        Uses pgvector's cosine distance to find the most similar memories
        to the query text.

        Args:
            query: The search query text.
            k: Number of results to return (default 5).

        Returns:
            list[Memory]: List of memories sorted by similarity.
        """
        query_embedding = await get_embedding(query)

        result = await self._db.execute(
            select(Memory)
            .where(Memory.user_id == self._user.id)
            .order_by(Memory.embedding.cosine_distance(query_embedding.tolist()))
            .limit(k)
        )
        return list(result.scalars().all())

    async def get_memories_for_record(self, record_id: UUID) -> list[Memory]:
        """Get all memories associated with a record.

        Args:
            record_id: UUID of the record.

        Returns:
            list[Memory]: List of memories linked to the record.
        """
        result = await self._db.execute(
            select(Memory).where(
                Memory.user_id == self._user.id,
                Memory.source_id == record_id,
            )
        )
        return list(result.scalars().all())

    async def delete_memory(self, memory_id: UUID) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: UUID of the memory to delete.

        Returns:
            bool: True if deleted, False if not found.
        """
        result = await self._db.execute(
            select(Memory).where(
                Memory.id == memory_id,
                Memory.user_id == self._user.id,
            )
        )
        memory = result.scalar_one_or_none()
        if memory:
            await self._db.delete(memory)
            await self._db.commit()
            return True
        return False

    async def delete_memories_for_record(self, record_id: UUID) -> int:
        """Delete all memories associated with a record.

        Args:
            record_id: UUID of the record.

        Returns:
            int: Number of memories deleted.
        """
        result = await self._db.execute(
            select(Memory).where(
                Memory.user_id == self._user.id,
                Memory.source_id == record_id,
            )
        )
        memories = result.scalars().all()
        count = len(memories)
        for memory in memories:
            await self._db.delete(memory)
        await self._db.commit()
        return count
