"""Release data models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Release(BaseModel):
    """Represents a single product release / version."""

    id: str
    product_id: str
    version: str
    title: str
    published_at: datetime | None
    source_url: str
    source_type: str
    source_hash: str
    raw_snapshot_path: str | None = None
    normalized_snapshot_path: str | None = None
    discovered_at: datetime
