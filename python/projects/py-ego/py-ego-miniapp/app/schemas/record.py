from datetime import date, datetime
from uuid import UUID
from pydantic import BaseModel
from enum import Enum


class ContentType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    PHOTO = "photo"


class RecordCreate(BaseModel):
    content_type: ContentType
    content: str | None = None
    media_url: str | None = None


class RecordResponse(BaseModel):
    id: UUID
    content_type: str
    content: str | None = None
    media_url: str | None = None
    record_date: date
    created_at: datetime

    class Config:
        from_attributes = True