"""Stable URL identity for Radar items."""

from __future__ import annotations

import hashlib
from typing import Any
from urllib.parse import urlsplit

from backend._shared.urls import normalize_url


def canonicalize_radar_url(url: str) -> str:
    """Return the canonical URL used for Radar deduplication and storage."""
    normalized = normalize_url(url)
    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"Invalid Radar URL: {url!r}")
    return normalized


def radar_item_id(url: str) -> str:
    """Generate the stable Radar item ID from its canonical URL."""
    canonical_url = canonicalize_radar_url(url)
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()[:16]


def deduplicate_radar_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge repeated canonical URLs while preserving the richest item fields."""
    unique: dict[str, dict[str, Any]] = {}
    for source in items:
        try:
            key = canonicalize_radar_url(str(source.get("url") or ""))
        except ValueError:
            key = str(source.get("id") or "")
        if not key:
            continue

        incoming = dict(source)
        incoming["url"] = key if key.startswith(("http://", "https://")) else incoming.get("url", "")
        existing = unique.get(key)
        if existing is None:
            unique[key] = incoming
            continue

        for field in ("title", "originalTitle", "original_title", "product", "contentType", "content_type"):
            if not existing.get(field) and incoming.get(field):
                existing[field] = incoming[field]
        for field in ("summary", "rawContent", "raw_content"):
            if len(str(incoming.get(field) or "")) > len(str(existing.get(field) or "")):
                existing[field] = incoming[field]
        for field in ("tags", "sources"):
            existing[field] = list(dict.fromkeys([*(existing.get(field) or []), *(incoming.get(field) or [])]))

    return list(unique.values())
