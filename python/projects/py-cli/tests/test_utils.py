"""Tests for utility functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from py_cli.utils import (
    format_date,
    format_duration,
    get_default_output_path,
    parse_date,
    sanitize_filename,
    truncate_text,
)


class TestParseDate:
    """Tests for parse_date function."""

    def test_parse_valid_date(self) -> None:
        """Test parsing a valid date string."""
        result = parse_date("2024-01-15")

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.tzinfo == timezone.utc

    def test_parse_none_returns_default(self) -> None:
        """Test that None returns a date in the past."""
        result = parse_date(None, default_days=30)

        # Should be approximately 30 days ago
        now = datetime.now(timezone.utc)
        delta = now - result

        assert 29 <= delta.days <= 31

    def test_parse_invalid_date_raises(self) -> None:
        """Test that invalid date format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid date format"):
            parse_date("15-01-2024")


class TestFormatDate:
    """Tests for format_date function."""

    def test_format_date(self) -> None:
        """Test formatting a datetime."""
        dt = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_date(dt)

        assert result == "2024-01-15"


class TestTruncateText:
    """Tests for truncate_text function."""

    def test_text_shorter_than_max(self) -> None:
        """Test that short text is not truncated."""
        text = "Short text"
        result = truncate_text(text, 100)

        assert result == text

    def test_text_longer_than_max(self) -> None:
        """Test that long text is truncated."""
        text = "This is a long text that needs truncation"
        result = truncate_text(text, 20)

        assert len(result) <= 20
        assert result.endswith("...")

    def test_custom_suffix(self) -> None:
        """Test custom truncation suffix."""
        text = "This is a long text"
        result = truncate_text(text, 15, suffix="[more]")

        assert "[more]" in result


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_removes_unsafe_chars(self) -> None:
        """Test that unsafe characters are replaced."""
        result = sanitize_filename("file/name:with|unsafe*chars?")

        assert "/" not in result
        assert ":" not in result
        assert "|" not in result

    def test_collapse_multiple_underscores(self) -> None:
        """Test that multiple underscores are collapsed."""
        result = sanitize_filename("file___name")

        assert "___" not in result

    def test_empty_result_fallback(self) -> None:
        """Test fallback for empty sanitized name."""
        result = sanitize_filename("...")

        assert result == "report"


class TestGetDefaultOutputPath:
    """Tests for get_default_output_path function."""

    def test_generates_path_with_timestamp(self) -> None:
        """Test that path includes timestamp and repo name."""
        repo_path = Path("/path/to/my-repo")
        result = get_default_output_path(repo_path)

        assert "my-repo" in result.name
        assert "analysis" in result.name
        assert result.suffix == ".md"


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_seconds_format(self) -> None:
        """Test formatting seconds."""
        result = format_duration(45.5)

        assert result.endswith("s")
        assert "45" in result

    def test_minutes_format(self) -> None:
        """Test formatting minutes."""
        result = format_duration(125.0)

        assert result.endswith("m")

    def test_hours_format(self) -> None:
        """Test formatting hours."""
        result = format_duration(3700.0)

        assert result.endswith("h")
