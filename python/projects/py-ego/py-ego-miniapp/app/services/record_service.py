"""Record service for daily record CRUD operations.

This module provides the RecordService class that handles:
- Creating daily records
- Retrieving records with pagination
- Deleting records
- Timeline data generation
"""

from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyRecord, User
from app.schemas import RecordCreate
from app.services.memory_service import MemoryService
from app.utils import NotFoundException


class RecordService:
    """Service handling daily record operations.

    This service manages all record-related operations for users:
    - Create new records (text, voice, photo)
    - Retrieve records with pagination
    - Delete records
    - Generate timeline data for calendar views

    Attributes:
        _db: SQLAlchemy async session for database operations.
        _user: The authenticated user performing operations.
    """

    def __init__(self, db: AsyncSession, user: User):
        """Initialize the record service.

        Args:
            db: SQLAlchemy async session for database operations.
            user: The authenticated user performing operations.
        """
        self._db = db
        self._user = user

    async def create_record(self, data: RecordCreate) -> DailyRecord:
        """Create a new daily record.

        Creates a record of the specified content type (text, voice, or photo)
        associated with the current user. Also creates a memory entry for
        semantic search if the record has text content.

        Args:
            data: Record creation data containing content_type, content,
                  and optional media_url.

        Returns:
            DailyRecord: The newly created record instance.
        """
        record = DailyRecord(
            user_id=self._user.id,
            content_type=data.content_type.value,
            content=data.content,
            media_url=data.media_url,
        )
        self._db.add(record)
        await self._db.commit()
        await self._db.refresh(record)

        # Create memory for text content
        if data.content:
            memory_service = MemoryService(self._db, self._user)
            await memory_service.add_memory(
                content=data.content,
                source_type="record",
                source_id=record.id,
            )

        return record

    async def get_records(
        self,
        page: int = 1,
        size: int = 20,
        record_date: Optional[date] = None,
    ) -> tuple[list[DailyRecord], int]:
        """Get paginated records for the current user.

        Retrieves records with optional filtering by date and returns
        both the records and total count for pagination.

        Args:
            page: Page number (1-indexed).
            size: Number of records per page.
            record_date: Optional date filter to retrieve records for a specific day.

        Returns:
            tuple[list[DailyRecord], int]: A tuple containing:
                - list[DailyRecord]: The paginated list of records.
                - int: Total count of records matching the filter.
        """
        query = select(DailyRecord).where(DailyRecord.user_id == self._user.id)

        if record_date:
            query = query.where(DailyRecord.record_date == record_date)

        query = query.order_by(DailyRecord.created_at.desc())

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self._db.execute(count_query)
        total = total_result.scalar() or 0

        # Paginate
        query = query.offset((page - 1) * size).limit(size)
        result = await self._db.execute(query)
        records = result.scalars().all()

        return list(records), total

    async def get_record(self, record_id: UUID) -> DailyRecord:
        """Get a single record by ID.

        Retrieves a specific record ensuring it belongs to the current user.

        Args:
            record_id: UUID of the record to retrieve.

        Returns:
            DailyRecord: The requested record instance.

        Raises:
            NotFoundException: If the record doesn't exist or doesn't belong
                              to the current user.
        """
        result = await self._db.execute(
            select(DailyRecord).where(
                DailyRecord.id == record_id,
                DailyRecord.user_id == self._user.id,
            )
        )
        record = result.scalar_one_or_none()

        if not record:
            raise NotFoundException("Record not found")

        return record

    async def delete_record(self, record_id: UUID) -> None:
        """Delete a record.

        Removes a record from the database after verifying ownership.
        Also deletes associated memories.

        Args:
            record_id: UUID of the record to delete.

        Raises:
            NotFoundException: If the record doesn't exist or doesn't belong
                              to the current user.
        """
        record = await self.get_record(record_id)

        # Delete associated memories
        memory_service = MemoryService(self._db, self._user)
        await memory_service.delete_memories_for_record(record_id)

        await self._db.delete(record)
        await self._db.commit()

    async def get_timeline(self, year: int, month: int) -> list[dict]:
        """Get timeline data for a specific month.

        Retrieves all records for the specified month and groups them by date,
        providing a summary view suitable for calendar/timeline displays.

        Args:
            year: Year to query (e.g., 2026).
            month: Month to query (1-12).

        Returns:
            list[dict]: List of daily summaries, each containing:
                - date: ISO format date string (YYYY-MM-DD).
                - count: Number of records for that day.
                - preview: Text preview of the first record content.
        """
        query = (
            select(DailyRecord)
            .where(
                DailyRecord.user_id == self._user.id,
                extract("year", DailyRecord.record_date) == year,
                extract("month", DailyRecord.record_date) == month,
            )
            .order_by(DailyRecord.record_date.desc())
        )

        result = await self._db.execute(query)
        records = result.scalars().all()

        # Group by date
        timeline: dict[str, dict] = {}
        for record in records:
            if record.record_date is None:
                continue
            date_str = record.record_date.isoformat()
            if date_str not in timeline:
                timeline[date_str] = {"date": date_str, "count": 0, "preview": None}
            timeline[date_str]["count"] += 1
            if not timeline[date_str]["preview"] and record.content:
                preview = record.content[:50]
                if len(record.content) > 50:
                    preview += "..."
                timeline[date_str]["preview"] = preview

        return list(timeline.values())