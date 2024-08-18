"""Pydantic models for py-ego data structures."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class Memory(BaseModel):
    """A single memory entry with text and timestamp."""

    text: str = Field(..., description="The memory text content")
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="ISO 8601 timestamp when the memory was created",
    )

    @field_validator("text", mode="before")
    @classmethod
    def clean_text(cls, v: Any) -> str:
        """Clean text by removing invalid characters."""
        if v is None:
            return ""
        text = str(v)
        text = text.encode("utf-8", "ignore").decode("utf-8")
        text = "".join(
            char
            for char in text
            if char == "\n" or char == "\t" or (32 <= ord(char) <= 0x10FFFF)
        )
        return text.strip()


class ChatMessage(BaseModel):
    """A chat message in the conversation."""

    role: str = Field(..., description="Message role: 'system', 'user', or 'assistant'")
    content: str = Field(..., description="Message content")

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, v: str) -> str:
        valid_roles = {"system", "user", "assistant"}
        if v not in valid_roles:
            raise ValueError(f"Invalid role: {v}. Must be one of {valid_roles}")
        return v

    @field_validator("content", mode="before")
    @classmethod
    def clean_content(cls, v: Any) -> str:
        if v is None:
            return ""
        text = str(v)
        text = text.encode("utf-8", "ignore").decode("utf-8")
        text = "".join(
            char
            for char in text
            if char == "\n" or char == "\t" or (32 <= ord(char) <= 0x10FFFF)
        )
        return text.strip()


class UserProfile(BaseModel):
    """User profile containing learned information about the user."""

    content: str = Field(default="", description="Profile content in markdown format")
    last_updated: datetime | None = Field(
        default=None, description="When the profile was last updated"
    )

    def is_empty(self) -> bool:
        """Check if the profile is empty."""
        return not self.content.strip()