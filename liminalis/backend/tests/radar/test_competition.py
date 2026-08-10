"""Tests for CompetitionAnalyzer."""

from __future__ import annotations

from unittest.mock import patch

from backend._shared.llm import CompletionResponse, LLMError
from backend.radar.intelligence.competition import CompetitionAnalyzer
from backend.radar.intelligence.types import CompetitiveInsight, ToolResult


def _completion(raw: dict) -> CompletionResponse:
    return CompletionResponse(text=raw["choices"][0]["message"]["content"], raw=raw)


class TestCompetitionAnalyzer:
    """Tests for CompetitionAnalyzer class."""

    def test_init_defaults(self):
        """Test CompetitionAnalyzer initialization with defaults."""
        analyzer = CompetitionAnalyzer()
        assert analyzer.client is not None

    def test_close(self):
        """Test that close properly closes HTTP client."""
        analyzer = CompetitionAnalyzer()
        analyzer.close()
        assert True

    def test_analyze_single_product(self, sample_summary_result):
        """Test analyze returns empty result with single product."""
        # Modify summary to have only one product
        sample_summary_result.top_updates = [
            {
                "product": "Snowflake",
                "title": "Single update",
                "what_changed": ["Change 1"],
                "why_it_matters": ["Matters 1"],
                "sources": ["url"],
            }
        ]

        analyzer = CompetitionAnalyzer()
        result = analyzer.analyze(sample_summary_result)

        assert result.success is True
        assert result.data == []  # Need at least 2 products

    def test_analyze_empty_products(self, sample_summary_result):
        """Test analyze handles empty product list."""
        sample_summary_result.top_updates = []

        analyzer = CompetitionAnalyzer()
        result = analyzer.analyze(sample_summary_result)

        assert result.success is True
        assert result.data == []

    @patch("backend.radar.intelligence.competition.SyncLLMClient.complete")
    def test_analyze_multiple_products(
        self,
        mock_complete,
        sample_summary_result,
        mock_llm_response_competition: dict,
    ):
        """Test analyze with multiple products and mocked LLM response."""
        mock_complete.return_value = _completion(mock_llm_response_competition)

        analyzer = CompetitionAnalyzer()
        result = analyzer.analyze(sample_summary_result)

        assert result.success is True
        assert result.data is not None
        assert len(result.data) == 2
        assert isinstance(result.data[0], CompetitiveInsight)
        assert result.data[0].product == "Snowflake"

    @patch("backend.radar.intelligence.competition.SyncLLMClient.complete")
    def test_analyze_custom_products(
        self,
        mock_complete,
        sample_summary_result,
        mock_llm_response_competition: dict,
    ):
        """Test analyze with custom products set."""
        mock_complete.return_value = _completion(mock_llm_response_competition)

        analyzer = CompetitionAnalyzer()
        custom_products = {"ProductA", "ProductB"}
        result = analyzer.analyze(sample_summary_result, products=custom_products)

        assert result.success is True

    @patch("backend.radar.intelligence.competition.SyncLLMClient.complete")
    def test_analyze_handles_llm_error(
        self,
        mock_complete,
        sample_summary_result,
    ):
        """Test analyze handles LLM errors gracefully."""
        mock_complete.side_effect = LLMError("API error")

        analyzer = CompetitionAnalyzer()
        result = analyzer.analyze(sample_summary_result)

        assert result.success is False
        assert result.error is not None

    @patch("backend.radar.intelligence.competition.SyncLLMClient.complete")
    def test_analyze_handles_malformed_response(
        self,
        mock_complete,
        sample_summary_result,
    ):
        """Test analyze handles malformed LLM responses."""
        mock_complete.return_value = CompletionResponse(text="not valid json", raw={})

        analyzer = CompetitionAnalyzer()
        result = analyzer.analyze(sample_summary_result)

        # Should fail gracefully
        assert result.success is False


class TestCompetitiveInsight:
    """Tests for CompetitiveInsight dataclass."""

    def test_creation(self):
        """Test CompetitiveInsight creation."""
        insight = CompetitiveInsight(
            product="Snowflake",
            recent_moves=["Move 1", "Move 2"],
            positioning_changes=["Change 1"],
            competitive_threats=["Threat 1"],
            opportunities=["Opportunity 1"],
        )

        assert insight.product == "Snowflake"
        assert len(insight.recent_moves) == 2
        assert len(insight.positioning_changes) == 1

    def test_defaults(self):
        """Test CompetitiveInsight default values."""
        insight = CompetitiveInsight(product="TestProduct")

        assert insight.recent_moves == []
        assert insight.positioning_changes == []
        assert insight.competitive_threats == []
        assert insight.opportunities == []

    def test_to_dict(self, sample_competitive_insights: list[CompetitiveInsight]):
        """Test CompetitiveInsight.to_dict() method."""
        insight = sample_competitive_insights[0]
        data = insight.to_dict()

        assert data["product"] == "Snowflake"
        assert "recent_moves" in data
        assert "positioning_changes" in data
        assert "competitive_threats" in data
        assert "opportunities" in data


class TestToolResult:
    """Tests for ToolResult wrapper class."""

    def test_ok(self):
        """Test ToolResult.ok() factory method."""
        result = ToolResult.ok(data="test data")

        assert result.success is True
        assert result.data == "test data"
        assert result.error is None

    def test_fail(self):
        """Test ToolResult.fail() factory method."""
        result = ToolResult.fail("test error")

        assert result.success is False
        assert result.data is None
        assert result.error == "test error"

    def test_ok_with_none_data(self):
        """Test ToolResult.ok() with None data."""
        result = ToolResult.ok(data=None)

        assert result.success is True
        assert result.data is None
