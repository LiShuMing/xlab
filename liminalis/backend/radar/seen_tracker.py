"""Track seen articles for incremental subscription."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from backend._shared.serializers import parse_datetime, utc_now, utc_now_iso
from backend._shared.storage import runtime_cache_path


@dataclass
class SeenArticle:
    """Record of a seen article."""

    url: str
    title: str
    first_seen: str  # ISO timestamp
    last_seen: str  # ISO timestamp (updated on subsequent runs)
    published_at: str | None = None


class SeenTracker:
    """
    Track articles that have been processed to enable incremental updates.

    Uses a JSON file to persist seen article URLs with metadata.
    """

    def __init__(self, seen_file: Path):
        self.seen_file = seen_file
        self._seen: dict[str, SeenArticle] = {}
        self._load()

    def _get_url_hash(self, url: str) -> str:
        """Generate a hash for the URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    def _load(self) -> None:
        """Load seen articles from file."""
        if not self.seen_file.exists():
            return

        try:
            data = json.loads(self.seen_file.read_text(encoding="utf-8"))
            for key, item in data.items():
                self._seen[key] = SeenArticle(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    first_seen=item.get("first_seen", ""),
                    last_seen=item.get("last_seen", ""),
                    published_at=item.get("published_at"),
                )
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Failed to load seen articles: {e}")

    def _save(self) -> None:
        """Save seen articles to file."""
        data = {}
        for key, article in self._seen.items():
            data[key] = {
                "url": article.url,
                "title": article.title,
                "first_seen": article.first_seen,
                "last_seen": article.last_seen,
                "published_at": article.published_at,
            }

        self.seen_file.parent.mkdir(parents=True, exist_ok=True)
        self.seen_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def is_seen(self, url: str) -> bool:
        """Check if an article URL has been seen before."""
        key = self._get_url_hash(url)
        return key in self._seen

    def mark_seen(self, url: str, title: str, published_at: str | None = None) -> None:
        """
        Mark an article as seen.

        Args:
            url: Article URL.
            title: Article title.
            published_at: Optional publication date.
        """
        key = self._get_url_hash(url)
        now = utc_now_iso()

        if key in self._seen:
            # Update last_seen timestamp
            existing = self._seen[key]
            self._seen[key] = SeenArticle(
                url=existing.url,
                title=title,
                first_seen=existing.first_seen,
                last_seen=now,
                published_at=published_at or existing.published_at,
            )
        else:
            # New article
            self._seen[key] = SeenArticle(
                url=url,
                title=title,
                first_seen=now,
                last_seen=now,
                published_at=published_at,
            )

    def mark_seen_batch(self, items: list) -> int:
        """
        Mark multiple items as seen.

        Args:
            items: List of items with 'url', 'title', 'published_at' attributes or dict keys.

        Returns:
            Number of new items (not previously seen).
        """
        new_count = 0
        for item in items:
            # Handle both dict and object
            if isinstance(item, dict):
                url = item.get("url", "")
                title = item.get("title", "")
                published_at = item.get("published_at")
            else:
                url = getattr(item, "url", "")
                title = getattr(item, "title", "")
                published_at = getattr(item, "published_at", None)

            if not url:
                continue

            if not self.is_seen(url):
                new_count += 1

            self.mark_seen(url, title, published_at)

        self._save()
        return new_count

    def filter_new(self, items: list) -> list:
        """
        Filter items to only include new (unseen) articles.

        Args:
            items: List of items with 'url' attribute or key.

        Returns:
            List of new items.
        """
        new_items = []
        for item in items:
            url = item.get("url", "") if isinstance(item, dict) else getattr(item, "url", "")

            if url and not self.is_seen(url):
                new_items.append(item)

        return new_items

    def get_stats(self) -> dict:
        """Get statistics about seen articles."""
        return {
            "total_seen": len(self._seen),
            "seen_file": str(self.seen_file),
        }

    def cleanup_old(self, days: int = 30) -> int:
        """
        Remove old entries that haven't been seen in N days.

        Args:
            days: Number of days to keep entries.

        Returns:
            Number of entries removed.
        """
        cutoff = utc_now()
        removed = 0

        keys_to_remove = []
        for key, article in self._seen.items():
            try:
                last_seen = parse_datetime(article.last_seen)
                if last_seen is None:
                    raise ValueError("invalid last_seen")
                age_days = (cutoff - last_seen).days
                if age_days > days:
                    keys_to_remove.append(key)
            except (ValueError, AttributeError):
                # Remove entries with invalid dates
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._seen[key]
            removed += 1

        if removed > 0:
            self._save()

        return removed


def get_seen_tracker() -> SeenTracker:
    """Get the default SeenTracker instance."""
    return SeenTracker(runtime_cache_path("radar", "seen_articles.json"))
