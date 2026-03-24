"""Role schema definitions.

This module defines Pydantic models for role-related API requests and responses.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RolePersonalityResponse(BaseModel):
    """Role personality response model."""

    background: str = Field(default="", description="Professional background")
    traits: list[str] = Field(default_factory=list, description="Personality traits")
    speaking_style: str = Field(default="", description="Communication style")
    catchphrases: list[str] = Field(default_factory=list, description="Signature phrases")


class RoleKnowledgeResponse(BaseModel):
    """Role knowledge response model."""

    domain_expertise: list[str] = Field(default_factory=list, description="Professional domains")
    key_concepts: list[str] = Field(default_factory=list, description="Core concepts")
    classic_quotes: list[str] = Field(default_factory=list, description="Quotable quotes")
    references: list[str] = Field(default_factory=list, description="Recommended resources")


class RoleExampleResponse(BaseModel):
    """Role example dialogue response model."""

    user_input: str = Field(..., description="Example user message")
    assistant_response: str = Field(..., description="Example assistant reply")
    context: str | None = Field(default=None, description="Situation context")


class RoleResponse(BaseModel):
    """Role summary response model.

    Used for listing roles without full details.
    """

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Display name in Chinese")
    icon: str = Field(..., description="Emoji icon")
    description: str = Field(..., description="Short description")


class RoleDetailResponse(BaseModel):
    """Detailed role response model.

    Includes full role configuration including personality, knowledge, and examples.
    """

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Display name in Chinese")
    icon: str = Field(..., description="Emoji icon")
    description: str = Field(..., description="Short description")
    system_prompt: str = Field(..., description="Base system prompt")
    personality: RolePersonalityResponse = Field(
        default_factory=RolePersonalityResponse,
        description="Role personality and speaking style",
    )
    knowledge: RoleKnowledgeResponse = Field(
        default_factory=RoleKnowledgeResponse,
        description="Role-specific knowledge base",
    )
    examples: list[RoleExampleResponse] = Field(
        default_factory=list,
        description="Few-shot dialogue examples",
    )
