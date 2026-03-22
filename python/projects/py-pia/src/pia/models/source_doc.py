"""Source document data models."""

from pydantic import BaseModel
from typing import Optional


class SourceDocument(BaseModel):
    """Represents a fetched source document."""

    id: str
    release_id: str
    url: str
    title: str
    kind: str  # official_release_note | official_blog | news | docs
    content_hash: str
    local_path: str


class NormalizedDoc(BaseModel):
    """Represents a normalized (cleaned) source document in markdown."""

    title: str
    published_at: Optional[str]
    headings: list[str]
    markdown_body: str
    extracted_links: list[str]
    content_hash: str
    source_url: str
