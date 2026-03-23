"""Rank normalized items by relevance and recency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from dbradar.normalize import NormalizedItem

if TYPE_CHECKING:
    from dbradar.interests import InterestsConfig


@dataclass
class RankedItem:
    """
    A ranked item with score and reasoning.

    Attributes:
        item: The normalized item being ranked.
        score: The computed relevance score.
        rank: Position in the ranked list (1-indexed).
        reasons: List of human-readable reasons for the score.
        boosted: Whether this item received a personalization boost.
        boost_reason: Description of why the item was boosted.
    """

    item: NormalizedItem
    score: float
    rank: int
    reasons: List[str]
    boosted: bool = False
    boost_reason: Optional[str] = None


class Ranker:
    """Rank items by relevance to DB/OLAP domain."""

    # Boost weights for different factors
    WEIGHT_RELEASE = 1.5
    WEIGHT_ENGINE = 1.3
    WEIGHT_PERFORMANCE = 1.4
    WEIGHT_DOCS = 0.8
    WEIGHT_RECENT = 1.2
    WEIGHT_OFFICIAL = 1.3

    # Keywords that boost relevance (fallback when no interests.keywords)
    HIGH_VALUE_KEYWORDS = [
        "performance", "execution", "optimizer", "query", "storage",
        "vectorized", "MPP", "columnar", "parquet", "index",
        "partition", "materialized view", "lakehouse", "serverless",
        "cost", "governance", "scan", "join", "aggregate",
        "benchmark", "latency", "throughput", "scale",
    ]

    def __init__(self, days: int = 7, interests: Optional[InterestsConfig] = None):
        """
        Initialize the ranker.

        Args:
            days: Number of days to consider for recency scoring.
            interests: Optional interests configuration for personalized ranking.
        """
        self.days = days
        self.interests = interests

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        try:
            if date_str == "unknown":
                return None
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            return None

    def _is_recent(self, item: NormalizedItem) -> bool:
        """Check if item is within the recency window."""
        dt = self._parse_date(item.published_at)
        if not dt:
            return False

        now = datetime.now(timezone.utc)
        age_days = (now - dt).total_seconds() / (24 * 3600)
        return age_days <= self.days

    def _calculate_recency_score(self, item: NormalizedItem) -> float:
        """Calculate recency score (1.0 for today, decreasing with age)."""
        dt = self._parse_date(item.published_at)
        if not dt:
            return 0.5  # Neutral for unknown dates

        now = datetime.now(timezone.utc)
        age_days = (now - dt).total_seconds() / (24 * 3600)

        if age_days < 0:
            return 0.5  # Future dates
        if age_days <= 1:
            return 1.0
        if age_days <= 3:
            return 0.9
        if age_days <= 7:
            return 0.8
        if age_days <= 14:
            return 0.6
        if age_days <= 30:
            return 0.4
        return 0.2

    def _calculate_content_score(self, item: NormalizedItem) -> float:
        """
        Calculate content relevance score.

        Note: This returns a 'relevance_score' (0.5-1.0), distinct from
        the 'content_score' variable in rank() which is a content-type weight.
        """
        text = f"{item.title} {item.content}".lower()
        score = 0.5  # Base score

        # Use personalized keywords if available, otherwise fall back to defaults
        if self.interests and self.interests.has_keywords():
            # Use interests.keywords with weighted scoring
            for kw, weight in self.interests.keywords.items():
                if kw in text:
                    score += 0.05 * weight
        else:
            # Fall back to HIGH_VALUE_KEYWORDS with flat +0.1
            for kw in self.HIGH_VALUE_KEYWORDS:
                if kw in text:
                    score += 0.1

        # Cap at 1.0
        return min(score, 1.0)

    def _calculate_source_score(self, item: NormalizedItem) -> float:
        """Calculate source authority score."""
        domain = item.domain.lower()

        # Official sources get higher scores
        official_patterns = [
            "github.com", "docs.", "official",
        ]
        if any(p in domain for p in official_patterns):
            return 1.2

        return 1.0

    def _get_product_boost(self, item: NormalizedItem) -> tuple[bool, Optional[str]]:
        """
        Check if item matches any product priority and return boost info.

        Uses "first match wins" rule based on YAML insertion order (dict preserves
        insertion order in Python 3.7+). Only checks title and domain to avoid
        false positives from comparative articles.

        Args:
            item: The normalized item to check.

        Returns:
            Tuple of (is_boosted, boost_reason).
        """
        if not self.interests or not self.interests.has_products():
            return False, None

        title_lower = item.title.lower()
        domain_lower = item.domain.lower()

        for product, weight in self.interests.products.items():
            # Check title and domain only (not content to avoid false positives)
            if product in title_lower or product in domain_lower:
                return True, f"{product.title()} (×{weight})"

        return False, None

    def rank(self, items: List[NormalizedItem], max_items: int = 80) -> List[RankedItem]:
        """
        Rank items by relevance.

        Args:
            items: List of normalized items.
            max_items: Maximum number of items to return.

        Returns:
            List of ranked items.
        """
        if not items:
            return []

        ranked: List[RankedItem] = []

        for item in items:
            reasons = []

            # Content type weight (content_score = type multiplier)
            content_score = 1.0
            if item.content_type == "release":
                content_score = self.WEIGHT_RELEASE
                reasons.append("Release note")
            elif item.content_type == "engine":
                content_score = self.WEIGHT_ENGINE
                reasons.append("Execution engine content")
            elif item.content_type == "performance":
                content_score = self.WEIGHT_PERFORMANCE
                reasons.append("Performance content")
            elif item.content_type == "docs":
                content_score = self.WEIGHT_DOCS
                reasons.append("Documentation update")

            # Product boost (applies to content_score)
            boosted = False
            boost_reason = None
            if self.interests and self.interests.has_products():
                is_boosted, reason = self._get_product_boost(item)
                if is_boosted:
                    product_name = reason.split(" ")[0] if reason else ""
                    weight = self.interests.products.get(product_name.lower(), 1.0)
                    content_score *= weight
                    boosted = True
                    boost_reason = reason
                    reasons.append(f"★ boosted: {reason}")

            # Recency score
            recency_score = self._calculate_recency_score(item)
            if recency_score > 0.8:
                reasons.append("Recent (within 3 days)")
            elif recency_score > 0.6:
                reasons.append("Recent (within 7 days)")

            # Content relevance (relevance_score = keyword signal)
            relevance_score = self._calculate_content_score(item)
            if relevance_score > 0.8:
                reasons.append("High relevance keywords")

            # Source authority
            source_score = self._calculate_source_score(item)

            # Confidence from extractor
            confidence = item.confidence

            # Calculate final score
            score = (
                content_score * 0.3
                + recency_score * self.WEIGHT_RECENT * 0.25
                + relevance_score * 0.2
                + source_score * 0.1
                + confidence * 0.15
            )

            ranked.append(RankedItem(
                item=item,
                score=score,
                rank=0,
                reasons=reasons,
                boosted=boosted,
                boost_reason=boost_reason,
            ))

        # Sort by score descending
        ranked.sort(key=lambda x: x.score, reverse=True)

        # Assign ranks
        for i, r in enumerate(ranked):
            r.rank = i + 1

        return ranked[:max_items]

    def get_top_k(self, items: List[RankedItem], k: int = 10) -> List[RankedItem]:
        """Get top K items."""
        return items[:k]


def rank_items(
    items: List[NormalizedItem],
    days: int = 7,
    max_items: int = 80,
    interests: Optional[InterestsConfig] = None,
) -> List[RankedItem]:
    """
    Convenience function to rank items.

    Args:
        items: List of normalized items to rank.
        days: Number of days for recency window.
        max_items: Maximum number of items to return.
        interests: Optional interests configuration for personalized ranking.

    Returns:
        List of ranked items sorted by score.
    """
    ranker = Ranker(days=days, interests=interests)
    return ranker.rank(items, max_items=max_items)
