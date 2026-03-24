from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nickname: str | None = None
    avatar_url: str | None = None
    created_at: datetime