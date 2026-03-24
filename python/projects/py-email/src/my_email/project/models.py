"""
Project identification data models.
"""

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Project:
    """A project cluster with associated metadata."""

    id: str  # slugified project name
    name: str  # display name
    keywords: list[str] = field(default_factory=list)
    sender_domains: list[str] = field(default_factory=list)
    email_count: int = 0
    first_seen: date | None = None
    last_seen: date | None = None


@dataclass
class ProjectAssignment:
    """Assignment of an email to a project with reasoning."""

    message_id: str
    project_id: str
    confidence: float  # 0.0 - 1.0
    reasons: list[str] = field(default_factory=list)