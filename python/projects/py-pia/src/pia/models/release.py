"""Release data models."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class Release(BaseModel):
    """Represents a single product release / version."""

    id: str
    product_id: str
    version: str
    title: str
    published_at: Optional[datetime]
    source_url: str
    source_type: str
    source_hash: str
    raw_snapshot_path: Optional[str] = None
    normalized_snapshot_path: Optional[str] = None
    discovered_at: datetime
