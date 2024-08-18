"""Ego chat request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    role_id: str = "therapist"


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=800)


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    role_id: str | None = None
    role_label: str | None = None
    content: str
    created_at: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    role_id: str
    created_at: str
    updated_at: str
