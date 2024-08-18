"""Date and time utilities."""

from __future__ import annotations

from datetime import datetime, timezone

from dateutil import parser as dateutil_parser


def now_utc() -> datetime:
    """Return the current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def parse_date(s: str | None) -> datetime | None:
    """Parse a date string into a datetime object.

    Accepts most common date formats including ISO 8601.

    Args:
        s: Date string to parse, or None.

    Returns:
        Parsed datetime, or None if input is None or unparseable.
    """
    if not s:
        return None
    try:
        return dateutil_parser.parse(s)
    except Exception:
        return None


def format_iso(dt: datetime | None) -> str | None:
    """Format a datetime as an ISO 8601 string.

    Args:
        dt: Datetime to format, or None.

    Returns:
        ISO 8601 string, or None if input is None.
    """
    if dt is None:
        return None
    return dt.isoformat()
