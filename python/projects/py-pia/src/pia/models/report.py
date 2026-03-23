"""Report data models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Report(BaseModel):
    """Represents a generated analysis report for a single release."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    product_id: str
    release_id: str
    report_type: str  # deep_analysis | summary | digest
    model_name: str
    prompt_version: str
    content_md: str
    content_hash: str
    generated_at: datetime


class DigestReport(BaseModel):
    """Represents a multi-product digest report."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    report_type: str = "digest"
    product_ids: list[str]
    time_window: str
    model_name: str
    prompt_version: str
    content_md: str
    content_hash: str
    generated_at: datetime
