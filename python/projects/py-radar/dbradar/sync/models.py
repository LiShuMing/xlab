"""Data models for OSS sync functionality."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SyncMetadata:
    """Metadata for a sync operation.

    This is stored alongside the Parquet file to track sync details.
    """

    version: str = "1.0"
    exported_at: datetime = field(default_factory=datetime.now)
    file_name: str = ""
    file_size: int = 0
    item_count: int = 0
    date_range: List[str] = field(default_factory=list)
    checksum: str = ""  # SHA256 of the Parquet file
    since: Optional[datetime] = None  # Incremental from this time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "version": self.version,
            "exported_at": self.exported_at.isoformat(),
            "file_name": self.file_name,
            "file_size": self.file_size,
            "item_count": self.item_count,
            "date_range": self.date_range,
            "checksum": self.checksum,
            "since": self.since.isoformat() if self.since else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SyncMetadata:
        """Create from dictionary."""
        exported_at = data.get("exported_at", datetime.now().isoformat())
        if isinstance(exported_at, str):
            exported_at = datetime.fromisoformat(exported_at)

        since = data.get("since")
        if since and isinstance(since, str):
            since = datetime.fromisoformat(since)

        return cls(
            version=data.get("version", "1.0"),
            exported_at=exported_at,
            file_name=data.get("file_name", ""),
            file_size=data.get("file_size", 0),
            item_count=data.get("item_count", 0),
            date_range=data.get("date_range", []),
            checksum=data.get("checksum", ""),
            since=since,
        )

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> SyncMetadata:
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    def save(self, path: Path) -> None:
        """Save metadata to JSON file."""
        path.write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SyncMetadata:
        """Load metadata from JSON file."""
        return cls.from_json(path.read_text(encoding="utf-8"))


@dataclass
class SyncStatus:
    """Tracks the sync status for local/remote database."""

    last_sync_at: Optional[datetime] = None
    last_sync_file: Optional[str] = None
    total_synced_items: int = 0
    sync_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "last_sync_file": self.last_sync_file,
            "total_synced_items": self.total_synced_items,
            "sync_count": self.sync_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SyncStatus:
        """Create from dictionary."""
        last_sync_at = data.get("last_sync_at")
        if last_sync_at and isinstance(last_sync_at, str):
            last_sync_at = datetime.fromisoformat(last_sync_at)

        return cls(
            last_sync_at=last_sync_at,
            last_sync_file=data.get("last_sync_file"),
            total_synced_items=data.get("total_synced_items", 0),
            sync_count=data.get("sync_count", 0),
        )

    def save(self, path: Path) -> None:
        """Save status to JSON file."""
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> SyncStatus:
        """Load status from JSON file."""
        if not path.exists():
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def compute_file_checksum(file_path: Path) -> str:
    """Compute SHA256 checksum of a file.

    Args:
        file_path: Path to the file

    Returns:
        Hex digest of SHA256 hash
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"
