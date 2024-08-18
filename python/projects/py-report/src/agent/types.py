"""Type definitions for the agent-based research pipeline."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ResearchMode(str, Enum):
    """Research mode determines which tools are enabled."""

    STANDARD = "standard"  # Base report only
    DEEP = "deep"  # All tools enabled
    EXECUTIVE = "executive"  # Condensed with competitive focus
    VERIFIED = "verified"  # Base + fact verification only


class ResearchOptions(BaseModel):
    """Configuration for agent-based research."""

    mode: ResearchMode = ResearchMode.DEEP
    enable_fact_verify: bool = True
    enable_competition: bool = True
    enable_history: bool = True
    enable_docs_analysis: bool = True
    competitors: List[str] = Field(default_factory=list)
    language: str = "English"
    depth: str = "deep"


class VerifiedFact(BaseModel):
    """A fact that has been verified via web search."""

    claim: str
    source_url: str
    source_snippet: str
    verification_status: str  # "verified", "partial", "contradicted", "unfound"
    confidence: float = Field(ge=0.0, le=1.0)


class CompetitiveInsight(BaseModel):
    """Competitive comparison for a specific dimension."""

    dimension: str  # e.g., "context_window", "pricing", "latency"
    comparisons: Dict[str, Any] = Field(default_factory=dict)  # product -> value
    analysis: str = ""


class VersionHistory(BaseModel):
    """Historical changes for an LLM API."""

    product: str
    versions: List[Dict[str, Any]] = Field(default_factory=list)
    deprecations: List[str] = Field(default_factory=list)
    pricing_changes: List[Dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def empty(cls, product: str) -> "VersionHistory":
        """Create an empty VersionHistory for a product."""
        return cls(product=product)


class TechnicalDocs(BaseModel):
    """Extracted technical documentation."""

    model_config = {"protected_namespaces": ()}

    model_cards: List[Dict[str, Any]] = Field(default_factory=list)
    api_endpoints: List[str] = Field(default_factory=list)
    sdk_examples: Dict[str, str] = Field(default_factory=dict)
    rate_limits: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def empty(cls) -> "TechnicalDocs":
        """Create an empty TechnicalDocs."""
        return cls()


class ToolResult(BaseModel):
    """Wrapper for tool results with error handling."""

    success: bool
    data: Any = None
    error: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    fallback_used: bool = False

    @classmethod
    def ok(cls, data: Any, sources: List[str] | None = None) -> "ToolResult":
        """Create a successful result."""
        return cls(success=True, data=data, sources=sources or [])

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        """Create a failed result."""
        return cls(success=False, error=error)


class ResearchReport(BaseModel):
    """Final synthesized report from ResearchAgent."""

    # Core content
    executive_summary: str = ""
    product_overview: Dict[str, Any] = Field(default_factory=dict)
    technical_deep_dive: Dict[str, Any] = Field(default_factory=dict)
    api_experience: Dict[str, Any] = Field(default_factory=dict)
    competitive_positioning: Dict[str, Any] = Field(default_factory=dict)
    use_cases: Dict[str, Any] = Field(default_factory=dict)
    ecosystem: Dict[str, Any] = Field(default_factory=dict)
    pricing: Dict[str, Any] = Field(default_factory=dict)
    recent_developments: Dict[str, Any] = Field(default_factory=dict)
    analyst_verdict: Dict[str, Any] = Field(default_factory=dict)

    # Agent-enhanced layers
    verified_facts: Optional[List[VerifiedFact]] = None
    competitive_insights: Optional[List[CompetitiveInsight]] = None
    version_history: Optional[VersionHistory] = None
    technical_docs: Optional[TechnicalDocs] = None

    # Raw markdown content (from base report)
    raw_markdown: str = ""

    # Metadata
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    research_mode: ResearchMode = ResearchMode.DEEP
    tools_used: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    product_name: str = ""

    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        if self.raw_markdown:
            return self.raw_markdown

        # Fallback: generate markdown from structured data
        lines = [
            f"# {self.product_name} Research Report",
            f"\n*Generated: {self.generated_at.isoformat()}*",
            f"*Mode: {self.research_mode.value}*",
            f"*Tools used: {', '.join(self.tools_used)}*\n",
            "## Executive Summary\n",
            self.executive_summary,
        ]
        return "\n".join(lines)

    @classmethod
    def from_markdown(
        cls, markdown: str, product_name: str, mode: ResearchMode = ResearchMode.DEEP
    ) -> "ResearchReport":
        """Create a ResearchReport from markdown content."""
        return cls(
            raw_markdown=markdown,
            product_name=product_name,
            research_mode=mode,
            executive_summary=_extract_section(markdown, "Executive Summary"),
        )


def _extract_section(markdown: str, section_name: str) -> str:
    """Extract a section from markdown by heading name."""
    import re

    pattern = rf"##\s*{re.escape(section_name)}\s*\n(.*?)(?=\n##|\Z)"
    match = re.search(pattern, markdown, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""