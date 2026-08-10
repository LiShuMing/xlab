"""Shared file-based cache for fetched web content."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from backend._shared.serializers import parse_datetime, utc_now, utc_now_iso


@dataclass
class CacheEntry:
    """Represents a cached web response."""

    url: str
    content_hash: str
    content: str
    etag: str | None = None
    last_modified: str | None = None
    fetched_at: str = field(default_factory=utc_now_iso)
    status_code: int = 200
    error: str | None = None


class Cache:
    """Simple file-based cache for HTTP responses."""

    def __init__(self, cache_dir: Path | str):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_url_hash(self, url: str) -> str:
        """Generate a short hash for the URL to use as filename."""
        return hashlib.md5(url.encode()).hexdigest()[:16]

    def _get_entry_path(self, url: str) -> Path:
        """Get the path for a cached entry."""
        return self.cache_dir / f"{self._get_url_hash(url)}.json"

    def get(self, url: str) -> CacheEntry | None:
        """Retrieve a cached entry for the given URL."""
        entry_path = self._get_entry_path(url)
        if not entry_path.exists():
            return None

        try:
            data = json.loads(entry_path.read_text())
            return CacheEntry(
                url=data["url"],
                content_hash=data["content_hash"],
                content=data["content"],
                etag=data.get("etag"),
                last_modified=data.get("last_modified"),
                fetched_at=data.get("fetched_at", ""),
                status_code=data.get("status_code", 200),
                error=data.get("error"),
            )
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def set(
        self,
        url: str,
        content: str,
        content_hash: str,
        etag: str | None = None,
        last_modified: str | None = None,
        status_code: int = 200,
        error: str | None = None,
    ) -> CacheEntry:
        """Store content in the cache."""
        entry = CacheEntry(
            url=url,
            content_hash=content_hash,
            content=content,
            etag=etag,
            last_modified=last_modified,
            fetched_at=utc_now_iso(),
            status_code=status_code,
            error=error,
        )

        entry_path = self._get_entry_path(url)
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        entry_path.write_text(
            json.dumps(
                {
                    "url": entry.url,
                    "content_hash": entry.content_hash,
                    "content": entry.content,
                    "etag": entry.etag,
                    "last_modified": entry.last_modified,
                    "fetched_at": entry.fetched_at,
                    "status_code": entry.status_code,
                    "error": entry.error,
                },
                indent=2,
            )
        )

        return entry

    def is_stale(self, url: str, max_age_hours: int = 24) -> bool:
        """Check if a cached entry is stale or missing."""
        entry = self.get(url)
        if entry is None:
            return True

        try:
            fetched_at = parse_datetime(entry.fetched_at)
            if fetched_at is None:
                return True
            now = utc_now()
            age = (now - fetched_at).total_seconds() / 3600
            return age > max_age_hours
        except (ValueError, AttributeError):
            return True

    def get_content_hash(self, content: str) -> str:
        """Generate a hash for content comparison."""
        return hashlib.sha256(content.encode()).hexdigest()
