"""Parse and manage RSS/Atom feed sources from feeds.json."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class FeedSource:
    """
    Represents an RSS/Atom feed source.

    Attributes:
        title: Human-readable name for the feed source.
        url: URL of the RSS/Atom feed.
        filter_tags: Optional list of tags to filter articles by.
            If specified, only articles with these tags will be included.
    """

    title: str
    url: str
    filter_tags: List[str] = field(default_factory=list)

    def has_filters(self) -> bool:
        """Check if this source has tag filters configured."""
        return bool(self.filter_tags)

    def matches_tags(self, tags: List[str]) -> bool:
        """
        Check if the given tags match this source's filter.

        Args:
            tags: List of tags from an article/feed entry.

        Returns:
            True if no filters configured (accept all), or if any tag matches.
        """
        if not self.has_filters():
            return True

        # Normalize tags for comparison
        filter_lower = [t.lower() for t in self.filter_tags]
        tags_lower = [t.lower() for t in tags]

        return any(t in filter_lower for t in tags_lower)


def parse_feeds_file(file_path: Path) -> List[FeedSource]:
    """
    Parse a feeds.json file and extract feed sources.

    Expected JSON format:
    [
        {
            "title": "Feed Name",
            "url": "https://example.com/feed.xml",
            "filter_tags": ["tag1", "tag2"]  // optional
        }
    ]

    Args:
        file_path: Path to the feeds.json file.

    Returns:
        List of FeedSource objects.
    """
    sources: List[FeedSource] = []

    if not file_path.exists():
        return sources

    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)

        if not isinstance(data, list):
            return sources

        for item in data:
            if not isinstance(item, dict):
                continue

            title = item.get("title", "")
            url = item.get("url", "")
            filter_tags = item.get("filter_tags", [])

            if not title or not url:
                continue

            # Ensure filter_tags is a list
            if not isinstance(filter_tags, list):
                filter_tags = []

            sources.append(FeedSource(
                title=title,
                url=url,
                filter_tags=filter_tags,
            ))

    except json.JSONDecodeError as e:
        print(f"Warning: Failed to parse {file_path}: {e}")
        return sources
    except Exception as e:
        print(f"Warning: Error reading {file_path}: {e}")
        return sources

    return sources


def get_feeds(feeds_file: Optional[Path] = None) -> List[FeedSource]:
    """
    Convenience function to get feed sources from the default feeds.json.

    Args:
        feeds_file: Optional custom path to feeds.json.

    Returns:
        List of FeedSource objects.
    """
    from dbradar.config import get_config

    config = get_config()
    path = feeds_file or config.feeds_file
    return parse_feeds_file(path)


def feeds_to_sources(feeds: List[FeedSource]) -> List["Source"]:
    """
    Convert FeedSource list to Source list for backward compatibility.

    This allows the existing fetcher pipeline to work with FeedSource data.

    Args:
        feeds: List of FeedSource objects.

    Returns:
        List of Source objects (each with one URL).
    """
    from dbradar.sources import Source

    sources: List[Source] = []
    for feed in feeds:
        sources.append(Source(
            product=feed.title,
            urls=[feed.url],
        ))
    return sources


if __name__ == "__main__":
    # Quick test
    feeds = parse_feeds_file(Path("feeds.json"))
    print(f"Found {len(feeds)} feed sources:")
    for f in feeds[:5]:
        print(f"  - {f.title}: {f.url}")
        if f.filter_tags:
            print(f"    Filter tags: {f.filter_tags}")
    if len(feeds) > 5:
        print(f"  ... and {len(feeds) - 5} more")