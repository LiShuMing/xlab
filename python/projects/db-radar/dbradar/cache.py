"""Simple file-based cache for fetched content."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class CacheEntry:
    """Represents a cached item."""

    url: str
    content_hash: str
    content: str
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status_code: int = 200
    error: Optional[str] = None


class Cache:
    """Simple file-based cache for HTTP responses."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self._index_file = cache_dir / "index.json"

    def _get_url_hash(self, url: str) -> str:
        """Generate a short hash for the URL to use as filename."""
        return hashlib.md5(url.encode()).hexdigest()[:16]

    def _get_entry_path(self, url: str) -> Path:
        """Get the path for a cached entry."""
        return self.cache_dir / f"{self._get_url_hash(url)}.json"

    def _load_index(self) -> dict:
        """Load the cache index."""
        if self._index_file.exists():
            try:
                return json.loads(self._index_file.read_text())
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    def _save_index(self, index: dict) -> None:
        """Save the cache index."""
        self._index_file.write_text(json.dumps(index, indent=2))

    def get(self, url: str) -> Optional[CacheEntry]:
        """
        Retrieve a cached entry for the given URL.

        Args:
            url: The URL to look up.

        Returns:
            CacheEntry if found and valid, None otherwise.
        """
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
        except (json.JSONDecodeError, KeyError, IOError):
            return None

    def set(
        self,
        url: str,
        content: str,
        content_hash: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
        status_code: int = 200,
        error: Optional[str] = None,
    ) -> CacheEntry:
        """
        Store content in the cache.

        Args:
            url: The URL that was fetched.
            content: The fetched content.
            content_hash: Hash of the content for change detection.
            etag: Optional ETag header from response.
            last_modified: Optional Last-Modified header.
            status_code: HTTP status code of the response.
            error: Optional error message if fetch failed.

        Returns:
            The created CacheEntry.
        """
        entry = CacheEntry(
            url=url,
            content_hash=content_hash,
            content=content,
            etag=etag,
            last_modified=last_modified,
            fetched_at=datetime.now(timezone.utc).isoformat(),
            status_code=status_code,
            error=error,
        )

        entry_path = self._get_entry_path(url)
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

        # Update index
        index = self._load_index()
        index[url] = {
            "path": str(entry_path),
            "fetched_at": entry.fetched_at,
            "content_hash": content_hash,
        }
        self._save_index(index)

        return entry

    def is_stale(self, url: str, max_age_hours: int = 24) -> bool:
        """
        Check if a cached entry is stale.

        Args:
            url: The URL to check.
            max_age_hours: Maximum age in hours before considering stale.

        Returns:
            True if the entry is stale or doesn't exist.
        """
        entry = self.get(url)
        if entry is None:
            return True

        try:
            fetched_at = datetime.fromisoformat(entry.fetched_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            age = (now - fetched_at).total_seconds() / 3600
            return age > max_age_hours
        except (ValueError, AttributeError):
            return True

    def get_content_hash(self, content: str) -> str:
        """Generate a hash for content comparison."""
        return hashlib.sha256(content.encode()).hexdigest()


def get_cache() -> Cache:
    """Get the default cache instance."""
    from dbradar.config import get_config

    config = get_config()
    return Cache(config.cache_dir)
