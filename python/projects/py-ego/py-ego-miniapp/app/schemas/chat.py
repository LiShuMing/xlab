from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class SessionCreate(BaseModel):
    role_id: str = "therapist"


class SessionResponse(BaseModel):
    id: UUID
    role_id: str
    started_at: datetime
    ended_at: datetime | None = None

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatReply(BaseModel):
    reply: str
    memories_used: int = 0