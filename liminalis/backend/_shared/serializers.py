"""Small serialization helpers shared by domain services."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse


def isoformat(value: Any) -> str | None:
    """Serialize date/datetime-like values to ISO strings."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return None if value is None else str(value)


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Return the current UTC timestamp as an ISO 8601 string."""
    return utc_now().isoformat()


def utc_timestamp_z(value: datetime | None = None) -> str:
    """Return a compact UTC timestamp with a trailing ``Z``."""
    value = value or utc_now()
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def date_key(value: date | datetime | None = None) -> str:
    """Return a stable YYYY-MM-DD key for dates and UTC datetimes."""
    value = value or utc_now()
    if isinstance(value, datetime):
        value = value.astimezone(UTC) if value.tzinfo is not None else value
        return value.strftime("%Y-%m-%d")
    return value.isoformat()


def parse_datetime(value: Any) -> datetime | None:
    """Parse common ISO-like datetime values into ``datetime`` objects."""
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def domain_from_url(url: str) -> str:
    """Return a display-friendly host from a URL."""
    if not url:
        return ""
    return urlparse(url).netloc.replace("www.", "") or ""


def compact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Drop keys with ``None`` values while preserving falsey business values."""
    return {key: value for key, value in data.items() if value is not None}
