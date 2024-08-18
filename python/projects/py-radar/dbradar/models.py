"""Pydantic models for structured LLM outputs.

This module defines all Pydantic models used for validating LLM outputs
according to Harness Engineering standards.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional


class TopUpdate(BaseModel):
    """A single top update entry."""

    product: str = Field(..., min_length=1, description="Product name")
    title: str = Field(..., min_length=1, description="Article title")
    what_changed: List[str] = Field(
        default_factory=list,
        description="List of concrete changes",
    )
    why_it_matters: List[str] = Field(
        default_factory=list,
        description="List of reasons why this matters",
    )
    sources: List[str] = Field(default_factory=list, description="Source URLs")
    evidence: List[str] = Field(default_factory=list, description="Evidence snippets")

    @field_validator("what_changed", "why_it_matters", "evidence")
    @classmethod
    def validate_non_empty_strings(cls, v: List[str]) -> List[str]:
        """Ensure all items in list are non-empty strings."""
        return [item.strip() for item in v if item and item.strip()]


class ReleaseNote(BaseModel):
    """A release note entry."""

    product: str = Field(..., min_length=1, description="Product name")
    version: Optional[str] = Field(None, description="Version info if available")
    date: Optional[str] = Field(None, description="Release date")
    highlights: List[str] = Field(default_factory=list, description="Key highlights")


class SummaryOutput(BaseModel):
    """Complete structured output from LLM summarization.

    This model validates the JSON structure returned by the LLM,
    ensuring all required fields are present and properly formatted.
    """

    executive_summary: List[str] = Field(
        ...,
        min_length=1,
        description="Executive summary bullets (max 5)",
    )
    top_updates: List[TopUpdate] = Field(
        default_factory=list,
        description="Detailed updates",
    )
    release_notes: List[ReleaseNote] = Field(
        default_factory=list,
        description="Release notes",
    )
    themes: List[str] = Field(
        default_factory=list,
        description="Broader industry themes",
    )
    action_items: List[str] = Field(
        default_factory=list,
        description="Concrete action items",
    )

    @field_validator("executive_summary")
    @classmethod
    def validate_max_5_bullets(cls, v: List[str]) -> List[str]:
        """Ensure executive summary has at most 5 bullets."""
        if len(v) > 5:
            return v[:5]
        return v

    @field_validator("executive_summary", "themes", "action_items")
    @classmethod
    def validate_non_empty(cls, v: List[str]) -> List[str]:
        """Filter out empty strings from lists."""
        return [item.strip() for item in v if item and item.strip()]


class TranslationOutput(BaseModel):
    """Output model for translation tasks."""

    executive_summary: List[str] = Field(default_factory=list)
    themes: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)


class TranslatedUpdate(BaseModel):
    """Translated version of TopUpdate."""

    product: str
    title: str
    what_changed: List[str]
    why_it_matters: List[str]
    evidence: List[str]


class TranslatedReleaseNote(BaseModel):
    """Translated version of ReleaseNote."""

    product: str
    version: Optional[str] = None
    highlights: List[str]
