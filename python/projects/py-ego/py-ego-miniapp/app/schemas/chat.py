from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class SessionCreate(BaseModel):
    role_id: str = "therapist"


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role_id: str
    started_at: datetime
    ended_at: datetime | None = None


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