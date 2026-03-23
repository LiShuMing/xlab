"""Type definitions for the intelligence module."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AnalysisMode(Enum):
    """Mode for intelligence analysis."""

    BASIC = "basic"  # Core summary only
    INTELLIGENCE = "intelligence"  # All tools enabled
    TRENDS = "trends"  # Trends + summary
    COMPETITION = "competition"  # Competition + summary


@dataclass
class AnalysisOptions:
    """Configuration for intelligence analysis."""

    mode: AnalysisMode = AnalysisMode.BASIC
    top_k: int = 10
    history_days: int = 14
    enable_trends: bool = False
    enable_competition: bool = False

    @classmethod
    def from_mode(cls, mode: AnalysisMode) -> "AnalysisOptions":
        """Create options from a mode."""
        return cls(
            mode=mode,
            enable_trends=mode in (AnalysisMode.TRENDS, AnalysisMode.INTELLIGENCE),
            enable_competition=mode in (AnalysisMode.COMPETITION, AnalysisMode.INTELLIGENCE),
        )


@dataclass
class TrendResult:
    """Result from trend detection analysis."""

    emerging_topics: List[str] = field(default_factory=list)
    declining_topics: List[str] = field(default_factory=list)
    recurring_themes: List[str] = field(default_factory=list)
    trend_velocity: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "TrendResult":
        """Create an empty trend result."""
        return cls()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "emerging_topics": self.emerging_topics,
            "declining_topics": self.declining_topics,
            "recurring_themes": self.recurring_themes,
            "trend_velocity": self.trend_velocity,
        }


@dataclass
class CompetitiveInsight:
    """Competitive insight for a single product."""

    product: str
    recent_moves: List[str] = field(default_factory=list)
    positioning_changes: List[str] = field(default_factory=list)
    competitive_threats: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "product": self.product,
            "recent_moves": self.recent_moves,
            "positioning_changes": self.positioning_changes,
            "competitive_threats": self.competitive_threats,
            "opportunities": self.opportunities,
        }


@dataclass
class ToolResult:
    """Wrapper for tool results with error handling."""

    success: bool
    data: Any = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, data: Any) -> "ToolResult":
        """Create a successful result."""
        return cls(success=True, data=data)

    @classmethod
    def fail(cls, error: str) -> "ToolResult":
        """Create a failed result."""
        return cls(success=False, error=error)


@dataclass
class IntelligenceReport:
    """Final synthesized report from IntelligenceAgent."""

    # Core summary
    executive_summary: List[str]
    top_updates: List[dict]
    release_notes: List[dict]
    themes: List[str]
    action_items: List[str]

    # Intelligence layer
    trends: Optional[TrendResult] = None
    competition: List[CompetitiveInsight] = field(default_factory=list)

    # Metadata
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    analysis_mode: AnalysisMode = AnalysisMode.BASIC
    tools_used: List[str] = field(default_factory=list)

    @classmethod
    def error(cls, error_message: str) -> "IntelligenceReport":
        """Create an error report when summarization fails."""
        return cls(
            executive_summary=[f"Error: {error_message}"],
            top_updates=[],
            release_notes=[],
            themes=[],
            action_items=[],
        )

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "executive_summary": self.executive_summary,
            "top_updates": self.top_updates,
            "release_notes": self.release_notes,
            "themes": self.themes,
            "action_items": self.action_items,
            "intelligence": {
                "trends": self.trends.to_dict() if self.trends else None,
                "competition": [c.to_dict() for c in self.competition],
            }
            if self.trends or self.competition
            else None,
            "metadata": {
                "generated_at": self.generated_at.isoformat(),
                "mode": self.analysis_mode.value,
                "tools_used": self.tools_used,
            },
        }