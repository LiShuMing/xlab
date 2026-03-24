from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: UUID
    nickname: str | None = None
    avatar_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True