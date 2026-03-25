"""Storage abstraction layer for DB Radar.

Provides a unified interface for storing and querying news items,
with pluggable backends (JSON files, DuckDB, etc.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Protocol


@dataclass
class StorageItem:
    """Unified item format for storage."""

    id: str  # Unique identifier (URL hash or UUID)
    url: str
    title: str  # Chinese title
    original_title: str  # English/original title
    published_date: Optional[date] = None
    product: str = ""
    content_type: str = "blog"  # release, benchmark, blog, news, tutorial
    summary: str = ""
    tags: List[str] = None
    sources: List[str] = None  # Additional source URLs
    fetched_at: datetime = None
    raw_content: str = ""  # Original HTML/text content

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.sources is None:
            self.sources = []
        if self.fetched_at is None:
            self.fetched_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
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
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> StorageItem:
        """Create from dictionary."""
        published = data.get("published_date")
        if published and isinstance(published, str):
            published = date.fromisoformat(published)

        fetched = data.get("fetched_at")
        if fetched and isinstance(fetched, str):
            fetched = datetime.fromisoformat(fetched)

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
        )


class ItemStore(ABC):
    """Abstract base class for item storage backends."""

    @abstractmethod
    def insert(self, items: List[StorageItem]) -> int:
        """Insert items into storage. Returns count inserted."""
        pass

    @abstractmethod
    def query(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        product: Optional[str] = None,
        content_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[StorageItem]:
        """Query items with filters."""
        pass

    @abstractmethod
    def get_by_date(self, target_date: date) -> List[StorageItem]:
        """Get all items for a specific date."""
        pass

    @abstractmethod
    def get_by_id(self, item_id: str) -> Optional[StorageItem]:
        """Get a single item by ID."""
        pass

    @abstractmethod
    def exists(self, url: str) -> bool:
        """Check if URL already exists."""
        pass

    @abstractmethod
    def get_date_range(self) -> tuple[Optional[date], Optional[date]]:
        """Get min and max dates in storage."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
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
