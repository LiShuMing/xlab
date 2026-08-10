"""Shared RSS/Atom feed parsing and detection helpers."""

from __future__ import annotations

import re
from typing import Any

import feedparser

FEED_URL_RE = re.compile(
    r"(/feed(?:/|$)|/rss(?:/|$)|\.rss(?:$|\?)|\.atom(?:$|\?)|feed\.xml(?:$|\?)|index\.xml(?:$|\?))",
    re.IGNORECASE,
)


def is_feed_url(url: str) -> bool:
    """Return True if a URL conventionally points to an RSS/Atom feed."""
    return bool(FEED_URL_RE.search(url or ""))


def parse_feed_content(content: str) -> Any:
    """Parse RSS/Atom content with Universal Feed Parser."""
    return feedparser.parse(content or "")


def is_parsed_feed(parsed: Any) -> bool:
    """Return True when feedparser recognized an RSS/Atom/RDF feed."""
    if not parsed:
        return False

    version = str(parsed.get("version") or "").strip()
    if version:
        return True

    entries = parsed.get("entries") or []
    feed = parsed.get("feed") or {}
    return bool(entries and (feed.get("title") or feed.get("link")))


def is_feed_content(content: str) -> bool:
    """Return True when content parses as RSS/Atom/RDF feed content."""
    try:
        return is_parsed_feed(parse_feed_content(content))
    except Exception:
        return False


def detect_content_type(
    url: str,
    content: str | None = None,
    *,
    assume_feed: bool = False,
) -> str:
    """Classify fetched web content as ``rss`` or ``html``."""
    if content is not None and is_feed_content(content):
        return "rss"
    if assume_feed or is_feed_url(url):
        return "rss"
    return "html"
