from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    current_role_id: str = "therapist"
    created_at: datetime
