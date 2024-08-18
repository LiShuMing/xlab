"""Pydantic models for structured LLM outputs.

This module defines all Pydantic models used for validating LLM outputs
according to Harness Engineering standards.
"""

from pydantic import BaseModel, Field, field_validator


class TopUpdate(BaseModel):
    """A single top update entry."""

    product: str = Field(..., min_length=1, description="Product name")
    title: str = Field(..., min_length=1, description="Article title")
    what_changed: list[str] = Field(
        default_factory=list,
        description="List of concrete changes",
    )
    why_it_matters: list[str] = Field(
        default_factory=list,
        description="List of reasons why this matters",
    )
    sources: list[str] = Field(default_factory=list, description="Source URLs")
    evidence: list[str] = Field(default_factory=list, description="Evidence snippets")

    @field_validator("what_changed", "why_it_matters", "evidence")
    @classmethod
    def validate_non_empty_strings(cls, v: list[str]) -> list[str]:
        """Ensure all items in list are non-empty strings."""
        return [item.strip() for item in v if item and item.strip()]


class ReleaseNote(BaseModel):
    """A release note entry."""

    product: str = Field(..., min_length=1, description="Product name")
    version: str | None = Field(None, description="Version info if available")
    date: str | None = Field(None, description="Release date")
    highlights: list[str] = Field(default_factory=list, description="Key highlights")


class SummaryOutput(BaseModel):
    """Complete structured output from LLM summarization.

    This model validates the JSON structure returned by the LLM,
    ensuring all required fields are present and properly formatted.
    """

    executive_summary: list[str] = Field(
        ...,
        min_length=1,
        description="Executive summary bullets (max 5)",
    )
    top_updates: list[TopUpdate] = Field(
        default_factory=list,
        description="Detailed updates",
    )
    release_notes: list[ReleaseNote] = Field(
        default_factory=list,
        description="Release notes",
    )
    themes: list[str] = Field(
        default_factory=list,
        description="Broader industry themes",
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="Concrete action items",
    )

    @field_validator("executive_summary")
    @classmethod
    def validate_max_5_bullets(cls, v: list[str]) -> list[str]:
        """Ensure executive summary has at most 5 bullets."""
        if len(v) > 5:
            return v[:5]
        return v

    @field_validator("executive_summary", "themes", "action_items")
    @classmethod
    def validate_non_empty(cls, v: list[str]) -> list[str]:
        """Filter out empty strings from lists."""
        return [item.strip() for item in v if item and item.strip()]


class TranslationOutput(BaseModel):
    """Output model for translation tasks."""

    executive_summary: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)


class TranslatedUpdate(BaseModel):
    """Translated version of TopUpdate."""

    product: str
    title: str
    what_changed: list[str]
    why_it_matters: list[str]
    evidence: list[str]


class TranslatedReleaseNote(BaseModel):
    """Translated version of ReleaseNote."""

    product: str
    version: str | None = None
    highlights: list[str]
