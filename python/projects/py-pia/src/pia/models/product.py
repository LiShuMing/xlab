"""Product data models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProductSource(BaseModel):
    """Represents a single data source for a product."""

    type: str  # github_releases | docs_html | rss
    url: str
    priority: int = 50


class ProductAnalysisConfig(BaseModel):
    """Configuration for LLM analysis of a product."""

    audience: list[str] = Field(default_factory=list)
    competitor_set: list[str] = Field(default_factory=list)
    prompt_profile: str = "database_olap"


class ProductVersionRules(BaseModel):
    """Rules for version parsing and normalization."""

    strategy: str = "semver_loose"


class Product(BaseModel):
    """Represents a tracked software product."""

    id: str
    name: str
    category: str  # open_source | commercial
    homepage: str
    description: str
    sources: list[ProductSource]
    analysis: ProductAnalysisConfig = Field(default_factory=ProductAnalysisConfig)
    version_rules: ProductVersionRules = Field(default_factory=ProductVersionRules)
    config_path: str | None = None
    created_at: datetime | None = None
