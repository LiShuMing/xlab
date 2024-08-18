"""Ego record request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class CreateRecordRequest(BaseModel):
    content_type: str = "text"
    content: str
    media_url: str | None = None


class RecordResponse(BaseModel):
    id: str
    content_type: str
    content: str
    media_url: str | None = None
    record_date: str
    created_at: str


class RecordListResponse(BaseModel):
    items: list[RecordResponse]


class TimelineDay(BaseModel):
    date: str
    count: int
    preview: str | None = None


class TimelineResponse(BaseModel):
    days: list[TimelineDay]
