"""Normalize and deduplicate extracted items."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from difflib import SequenceMatcher

from backend.radar.extractor import ExtractedItem


@dataclass
class NormalizedItem:
    """A normalized and deduplicated item."""

    # Core fields
    url: str
    product: str
    title: str
    content: str
    published_at: str | None

    # Normalized fields
    normalized_title: str
    domain: str
    date_hash: str  # YYYY-MM-DD or "unknown"

    # Metadata
    content_type: str
    confidence: float
    sources: list[str]  # Original URLs that merged into this

    # Evidence
    snippets: list[str]


class Normalizer:
    """Normalize and deduplicate extracted items."""

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    def normalize_title(self, title: str) -> str:
        """Normalize a title for comparison."""
        # Lowercase, remove special chars, normalize whitespace
        title = title.lower().strip()
        title = re.sub(r"[^\w\s]", "", title)
        title = re.sub(r"\s+", " ", title)
        return title

    def extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        domain = parsed.netloc.removeprefix("www.")
        return domain

    def parse_date(self, date_str: str | None) -> datetime | None:
        """Parse a date string into datetime."""
        if not date_str:
            return None

        # Normalize Z suffix for fromisoformat
        normalized = date_str.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        # Try ISO format first (covers most RSS/API dates)
        try:
            return datetime.fromisoformat(normalized)
        except (ValueError, AttributeError):
            pass

        # Try strptime for human-readable formats
        strptime_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%d %B %Y",
        ]
        for fmt in strptime_formats:
            try:
                return datetime.strptime(normalized, fmt).replace(tzinfo=UTC)
            except (ValueError, AttributeError):
                continue

        return None

    def extract_date_hash(self, item: ExtractedItem) -> str:
        """Extract YYYY-MM-DD from an item or return 'unknown'."""
        dt = self.parse_date(item.published_at)
        if dt:
            return dt.strftime("%Y-%m-%d")
        return "unknown"

    def extract_snippets(self, content: str, title: str, max_length: int = 200) -> list[str]:
        """Extract relevant snippets from content."""
        snippets = []

        # Find sentences containing keywords
        sentences = re.split(r"[.!?\n]", content)
        keywords = [
            "performance",
            "query",
            "execute",
            "optimize",
            "update",
            "feature",
            "release",
            "new",
            "improve",
            "storage",
            "engine",
            "support",
            "introduce",
            "announce",
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if (
                len(sentence) > 30
                and len(sentence) < max_length
                and any(kw in sentence.lower() for kw in keywords)
            ):
                snippets.append(sentence)

        return snippets[:3]  # Max 3 snippets

    def is_similar(self, title1: str, title2: str) -> bool:
        """Check if two titles are similar enough to be duplicates."""
        norm1 = self.normalize_title(title1)
        norm2 = self.normalize_title(title2)

        # Exact match after normalization
        if norm1 == norm2:
            return True

        # Sequence similarity
        ratio = SequenceMatcher(None, norm1, norm2).ratio()
        if ratio >= self.similarity_threshold:
            return True

        # Check if one is a substring of the other
        return bool(norm1 in norm2 or norm2 in norm1)

    def normalize(self, items: list[ExtractedItem]) -> list[NormalizedItem]:
        """
        Normalize and deduplicate a list of items.

        Args:
            items: List of extracted items.

        Returns:
            List of normalized, deduplicated items.
        """
        if not items:
            return []

        normalized: list[NormalizedItem] = []

        for item in items:
            # Skip error items with zero confidence
            if item.confidence <= 0:
                continue

            # Check for duplicates
            is_duplicate = False
            for _i, existing in enumerate(normalized):
                # Same URL
                if item.url == existing.url:
                    is_duplicate = True
                    break

                # Similar title + same product + same date
                if (
                    self.is_similar(item.title, existing.title)
                    and item.product == existing.product
                    and self.extract_date_hash(item) == existing.date_hash
                ):
                    # Merge sources
                    if item.url not in existing.sources:
                        existing.sources.append(item.url)
                    is_duplicate = True
                    break

            if is_duplicate:
                continue

            # Create normalized item
            norm_item = NormalizedItem(
                url=item.url,
                product=item.product,
                title=item.title,
                content=item.content,
                published_at=item.published_at,
                normalized_title=self.normalize_title(item.title),
                domain=self.extract_domain(item.url),
                date_hash=self.extract_date_hash(item),
                content_type=item.content_type,
                confidence=item.confidence,
                sources=[item.url],
                snippets=self.extract_snippets(item.content, item.title),
            )

            normalized.append(norm_item)

        # Sort by confidence and date
        normalized.sort(key=lambda x: (-x.confidence, x.date_hash))

        return normalized

    def filter_by_date(self, items: list[NormalizedItem], max_days: int = 7) -> list[NormalizedItem]:
        """Filter items to only include recent ones."""
        cutoff = datetime.now(UTC).timestamp() - (max_days * 24 * 60 * 60)

        filtered = []
        for item in items:
            dt = self.parse_date(item.published_at)
            if dt:
                if dt.timestamp() >= cutoff:
                    filtered.append(item)
            else:
                # Include items without dates but with high confidence
                if item.confidence > 0.7:
                    filtered.append(item)

        return filtered


def normalize_items(items: list[ExtractedItem]) -> list[NormalizedItem]:
    """Convenience function to normalize items."""
    normalizer = Normalizer()
    return normalizer.normalize(items)
