"""Storage abstraction layer for DB Radar.

Provides a unified interface for storing and querying news items,
with pluggable backends (JSON files, DuckDB, etc.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


@dataclass
class StorageItem:
    """Unified item format for storage."""

    id: str  # Unique identifier (URL hash or UUID)
    url: str
    title: str  # Chinese title
    original_title: str  # English/original title
    published_date: date | None = None
    product: str = ""
    content_type: str = "blog"  # release, benchmark, blog, news, tutorial
    summary: str = ""
    tags: list[str] = None
    sources: list[str] = None  # Additional source URLs
    fetched_at: datetime = None
    raw_content: str = ""  # Original HTML/text content
    sync_batch: date | None = None  # Date when item was synced

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.sources is None:
            self.sources = []
        if self.fetched_at is None:
            self.fetched_at = datetime.now()
        if self.sync_batch is None:
            self.sync_batch = date.today()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "original_title": self.original_title,
            "published_date": self.published_date.isoformat() if self.published_date else None,
            "product": self.product,
            "content_type": self.content_type,
            "summary": self.summary,
            "tags": self.tags,
            "sources": self.sources,
            "fetched_at": self.fetched_at.isoformat(),
            "sync_batch": self.sync_batch.isoformat() if self.sync_batch else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StorageItem:
        """Create from dictionary."""
        published = data.get("published_date")
        if published and isinstance(published, str):
            published = date.fromisoformat(published)

        fetched = data.get("fetched_at")
        if fetched and isinstance(fetched, str):
            fetched = datetime.fromisoformat(fetched)

        sync_batch = data.get("sync_batch")
        if sync_batch and isinstance(sync_batch, str):
            sync_batch = date.fromisoformat(sync_batch)

        return cls(
            id=data["id"],
            url=data["url"],
            title=data.get("title", ""),
            original_title=data.get("original_title", ""),
            published_date=published,
            product=data.get("product", ""),
            content_type=data.get("content_type", "blog"),
            summary=data.get("summary", ""),
            tags=data.get("tags", []),
            sources=data.get("sources", []),
            fetched_at=fetched or datetime.now(),
            sync_batch=sync_batch,
        )


class ItemStore(ABC):
    """Abstract base class for item storage backends."""

    @abstractmethod
    def insert(self, items: list[StorageItem]) -> int:
        """Insert items into storage. Returns count inserted."""
        pass

    @abstractmethod
    def query(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        product: str | None = None,
        content_type: str | None = None,
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[StorageItem]:
        """Query items with filters."""
        pass

    @abstractmethod
    def get_by_date(self, target_date: date) -> list[StorageItem]:
        """Get all items for a specific date."""
        pass

    @abstractmethod
    def get_by_id(self, item_id: str) -> StorageItem | None:
        """Get a single item by ID."""
        pass

    @abstractmethod
    def exists(self, url: str) -> bool:
        """Check if URL already exists."""
        pass

    @abstractmethod
    def get_date_range(self) -> tuple[date | None, date | None]:
        """Get min and max dates in storage."""
        pass

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close storage connection."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
