from __future__ import annotations
from datetime import datetime
from enum import IntEnum, StrEnum
from typing import Optional
from pydantic import BaseModel, Field


class Visibility(StrEnum):
    private = "private"
    match_only = "match_only"
    public = "public"
    friend_only = "friend_only"
    blocked = "blocked"


class Sensitivity(IntEnum):
    low = 0
    normal = 1
    sensitive = 2
    highly_sensitive = 3


class Purpose(StrEnum):
    self_memory = "self_memory"
    matching = "matching"
    generation = "generation"


class State(StrEnum):
    active = "active"
    pending_review = "pending_review"
    expired = "expired"
    deleted = "deleted"
    rejected = "rejected"


class ContextItem(BaseModel):
    id: str
    user_id: str
    type: str = ""
    text: str = ""
    visibility: Visibility = Visibility.match_only
    sensitivity: Sensitivity = Sensitivity.normal
    purpose: list[Purpose] = Field(default_factory=list)
    state: State = State.active
    source_asset_id: str = ""
    expires_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PhotoExtraction(BaseModel):
    text: str = ""
    topics: list[str] = Field(default_factory=list)
    sensitivity: Sensitivity = Sensitivity.normal
    confidence: float = 0.0
    privacy_flags: dict[str, bool] = Field(default_factory=dict)


class EmbeddingResult(BaseModel):
    embeddings: list[list[float]] = Field(default_factory=list)
    provider: str = ""
    model: str = ""
    fallback_used: bool = False
    error: str = ""
    latency_ms: int = 0


class BridgeResult(BaseModel):
    connection_reason: str = ""
    icebreakers: list[str] = Field(default_factory=list)
    provider: str = ""
    model: str = ""
    fallback_used: bool = False
    error: str = ""
    latency_ms: int = 0


class MatchResult(BaseModel):
    id: str
    user_id: str = ""
    target_user_id: str = ""
    target_handle: str = ""
    target_name: str = ""
    score: float = 0.0
    connection_reason: str = ""
    icebreakers: list[str] = Field(default_factory=list)
    context_ids: list[str] = Field(default_factory=list)
    safe_context_pack: dict = Field(default_factory=dict)
    bridge_result: dict = Field(default_factory=dict)
    privacy_check: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)


class SourceAsset(BaseModel):
    id: str
    user_id: str = ""
    asset_type: str = ""
    original_filename: str = ""
    visibility: Visibility = Visibility.private
    state: State = State.active
