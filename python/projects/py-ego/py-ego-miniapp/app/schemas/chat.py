from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    role_id: Optional[str] = Field(
        default=None,
        description="Role ID for the session. If not provided, uses user's current_role_id."
    )


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    created_at: datetime


class ChatReply(BaseModel):
    reply: str
    memories_used: int = 0
