"""Tests for TrendAnalyzer."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from dbradar.intelligence.trends import HistoricalSummary, TrendAnalyzer
from dbradar.intelligence.types import TrendResult


class TestTrendAnalyzer:
    """Tests for TrendAnalyzer class."""

    def test_init_defaults(self, temp_output_dir: Path):
        """Test TrendAnalyzer initialization with defaults."""
        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        assert analyzer.output_dir == temp_output_dir
        assert analyzer.client is not None

    def test_close(self, temp_output_dir: Path):
        """Test that close properly closes HTTP client."""
        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        analyzer.close()
        # Should not raise an error
        assert True

    def test_get_historical_summaries_empty_dir(self, temp_output_dir: Path):
        """Test get_historical_summaries with empty directory."""
        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        summaries = analyzer.get_historical_summaries(days=14, min_summaries=3)
        assert summaries == []

    def test_get_historical_summaries_with_data(
        self,
        temp_output_dir: Path,
        historical_summaries: list[dict],
    ):
        """Test get_historical_summaries with historical data."""
        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        summaries = analyzer.get_historical_summaries(days=14, min_summaries=3)

        # Should return summaries sorted by date (oldest first)
        assert len(summaries) == 7
        assert summaries[0].date < summaries[-1].date

    def test_get_historical_summaries_respects_min_summaries(
        self,
        temp_output_dir: Path,
    ):
        """Test that min_summaries threshold is respected."""
        analyzer = TrendAnalyzer(output_dir=temp_output_dir)

        # Create only 2 summary files
        for i in range(2):
            date_str = f"2024-01-{10 + i:02d}"
            data = {"themes": ["test"], "top_updates": []}
            (temp_output_dir / f"{date_str}.json").write_text(
                __import__('json').dumps(data)
            )

        # Should return empty list if not enough summaries
        summaries = analyzer.get_historical_summaries(days=14, min_summaries=3)
        assert summaries == []

    def test_has_history_true(
        self,
        temp_output_dir: Path,
        historical_summaries: list[dict],
    ):
        """Test has_history returns True when enough history exists."""
        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        assert analyzer.has_history(days=14, min_summaries=3) is True

    def test_has_history_false(self, temp_output_dir: Path):
        """Test has_history returns False when not enough history."""
        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        assert analyzer.has_history(days=14, min_summaries=3) is False

    def test_has_history_respects_days(
        self,
        temp_output_dir: Path,
        historical_summaries: list[dict],
    ):
        """Test has_history respects days parameter."""
        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        # If we only look back 1 day, we won't have enough data
        assert analyzer.has_history(days=1, min_summaries=3) is False

    def test_analyze_no_history(self, temp_output_dir: Path):
        """Test analyze returns empty result when no history."""
        # Create a sample summary result
        from dbradar.summarizer import SummaryResult
        summary = SummaryResult(
            executive_summary=["Test summary"],
            top_updates=[{"product": "Test", "title": "Test"}],
            release_notes=[],
            themes=["AI"],
            action_items=["Do something"],
            raw_response="{}",
        )

        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        result = analyzer.analyze(summary, history_days=14)

        assert result.success is True
        assert result.data is not None
        assert isinstance(result.data, TrendResult)
        # Empty trend result
        assert result.data.emerging_topics == []
        assert result.data.declining_topics == []

    @patch.object(httpx.Client, 'post')
    def test_analyze_with_history(
        self,
        mock_post,
        temp_output_dir: Path,
        historical_summaries: list[dict],
        mock_llm_response_trends: dict,
    ):
        """Test analyze with historical data and mocked LLM response."""
        # Create a sample summary result
        from dbradar.summarizer import SummaryResult
        summary = SummaryResult(
            executive_summary=["Test summary"],
            top_updates=[{"product": "Test", "title": "Test"}],
            release_notes=[],
            themes=["AI"],
            action_items=["Do something"],
            raw_response="{}",
        )

        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = mock_llm_response_trends
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        result = analyzer.analyze(summary, history_days=14)

        assert result.success is True
        assert result.data is not None
        assert isinstance(result.data, TrendResult)
        assert len(result.data.emerging_topics) == 2
        assert "Vector databases" in result.data.emerging_topics

    @patch.object(httpx.Client, 'post')
    def test_analyze_handles_llm_error(
        self,
        mock_post,
        temp_output_dir: Path,
        historical_summaries: list[dict],
    ):
        """Test analyze handles LLM errors gracefully."""
        # Create a sample summary result
        from dbradar.summarizer import SummaryResult
        summary = SummaryResult(
            executive_summary=["Test summary"],
            top_updates=[{"product": "Test", "title": "Test"}],
            release_notes=[],
            themes=["AI"],
            action_items=["Do something"],
            raw_response="{}",
        )

        # Mock an HTTP error
        mock_post.side_effect = httpx.HTTPError("API error")

        analyzer = TrendAnalyzer(output_dir=temp_output_dir)
        result = analyzer.analyze(summary, history_days=14)

        # Should return a failed result
        assert result.success is False
        assert result.error is not None


class TestHistoricalSummary:
    """Tests for HistoricalSummary dataclass."""

    def test_creation(self):
        """Test HistoricalSummary creation."""
        summary = HistoricalSummary(
            date="2024-01-15",
            themes=["AI", "Cloud"],
            top_products=["Snowflake", "Databricks"],
            top_titles=["Title 1", "Title 2"],
        )

        assert summary.date == "2024-01-15"
        assert len(summary.themes) == 2
        assert len(summary.top_products) == 2


class TestTrendResult:
    """Tests for TrendResult dataclass."""

    def test_empty(self):
        """Test TrendResult.empty() factory method."""
        result = TrendResult.empty()
        assert result.emerging_topics == []
        assert result.declining_topics == []
        assert result.recurring_themes == []
        assert result.trend_velocity == {}

    def test_to_dict(self, sample_trend_result: TrendResult):
        """Test TrendResult.to_dict() method."""
        data = sample_trend_result.to_dict()

        assert "emerging_topics" in data
        assert "declining_topics" in data
        assert "recurring_themes" in data
        assert "trend_velocity" in data
        assert len(data["emerging_topics"]) == 2