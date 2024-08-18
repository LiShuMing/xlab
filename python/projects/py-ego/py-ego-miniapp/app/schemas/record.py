from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from enum import Enum


class ContentType(str, Enum):
    TEXT = "text"
    VOICE = "voice"
    PHOTO = "photo"


class RecordCreate(BaseModel):
    content_type: ContentType
    content: Optional[str] = None
    media_url: Optional[str] = None


class RecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    content_type: str
    content: Optional[str] = None
    media_url: Optional[str] = None
    record_date: date
    created_at: datetime
