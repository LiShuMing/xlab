"""Product data models."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ProductSource(BaseModel):
    """Represents a single data source for a product."""

    type: str  # github_releases | docs_html | rss
    url: str
    priority: int = 50


class ProductAnalysisConfig(BaseModel):
    """Configuration for LLM analysis of a product."""

    audience: list[str] = []
    competitor_set: list[str] = []
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
    analysis: ProductAnalysisConfig = ProductAnalysisConfig()
    version_rules: ProductVersionRules = ProductVersionRules()
    config_path: Optional[str] = None
    created_at: Optional[datetime] = None
