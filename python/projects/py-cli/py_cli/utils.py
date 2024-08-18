"""General utilities for py-cli."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Final

# Date format patterns
ISO_DATE_FORMAT: Final = "%Y-%m-%d"
GIT_DATE_FORMAT: Final = "%Y-%m-%d %H:%M:%S %z"


def parse_date(date_str: str | None, default_days: int = 30) -> datetime:
    """Parse a date string or return a default date.

    Args:
        date_str: Date string in ISO format (YYYY-MM-DD) or None
        default_days: Number of days ago to use if date_str is None

    Returns:
        Datetime object in UTC timezone

    Raises:
        ValueError: If date_str is not in valid format
    """
    if date_str is None:
        return datetime.now(timezone.utc) - timedelta(days=default_days)

    try:
        dt = datetime.strptime(date_str, ISO_DATE_FORMAT)
        return dt.replace(tzinfo=timezone.utc)
    except ValueError as e:
        msg = f"Invalid date format: {date_str}. Use YYYY-MM-DD format."
        raise ValueError(msg) from e


def format_date(dt: datetime) -> str:
    """Format datetime to ISO date string."""
    return dt.strftime(ISO_DATE_FORMAT)


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length with suffix.

    Args:
        text: Input text
        max_length: Maximum allowed length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix


def sanitize_filename(name: str) -> str:
    """Sanitize a string for use as filename.

    Args:
        name: Input string

    Returns:
        Sanitized filename-safe string
    """
    # Replace unsafe characters with underscore
    safe = re.sub(r'[\\/*?:"<>|]', "_", name)
    # Collapse multiple underscores
    safe = re.sub(r"_+", "_", safe)
    # Strip leading/trailing whitespace and dots
    safe = safe.strip(" .")
    return safe or "report"


def get_default_output_path(repo_path: Path) -> Path:
    """Generate default output path for analysis report.

    Args:
        repo_path: Path to the git repository

    Returns:
        Default output file path
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    repo_name = sanitize_filename(repo_path.name)
    return Path.cwd() / f"{repo_name}_analysis_{timestamp}.md"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"
