"""Daily record model for storing user journal entries."""

import uuid
from datetime import date

from sqlalchemy import Column, Date, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base, GUID, TimestampMixin


class DailyRecord(Base, TimestampMixin):
    """Daily record model for user journal entries.

    Users can create text, voice, or photo records for each day.
    This serves as the primary input for AI analysis and memory.

    Attributes:
        id: UUID primary key.
        user_id: Reference to the User who created this record.
        content_type: Type of content - 'text', 'voice', or 'photo'.
        content: Text content (for text type or transcribed voice).
        media_url: URL to stored media file (voice/photo).
        record_date: The date this record represents.

    Relationships:
        user: Reference back to the User model.
    """

    __tablename__ = "daily_records"

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
    content_type = Column(
        String(10),
        nullable=False,
    )  # 'text', 'voice', 'photo'
    content = Column(Text)
    media_url = Column(String(500))
    record_date = Column(
        Date,
        default=date.today,
        index=True,
    )

    # Relationships
    user = relationship("User", back_populates="records")