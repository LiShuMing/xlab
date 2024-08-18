"""Tests for IntelligenceAgent orchestrator."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dbradar.intelligence.agent import AnalysisContext, IntelligenceAgent
from dbradar.intelligence.types import (
    AnalysisMode,
    AnalysisOptions,
    IntelligenceReport,
)
from dbradar.ranker import RankedItem
from dbradar.summarizer import SummaryResult


# Helper to create minimal RankedItem for testing
def create_mock_ranked_item(product: str = "TestProduct") -> RankedItem:
    """Create a mock RankedItem for testing."""
    from dbradar.normalize import NormalizedItem

    norm_item = NormalizedItem(
        url="https://example.com/test",
        product=product,
        title="Test Title",
        content="Test content",
        published_at="2024-01-15",
        normalized_title="test title",
        domain="example.com",
        date_hash="unknown",
        content_type="other",
        confidence=0.5,
        sources=["https://example.com/test"],
        snippets=[],
    )
    return RankedItem(item=norm_item, score=0.8, rank=1, reasons=[])


class TestAnalysisContext:
    """Tests for AnalysisContext dataclass."""

    def test_creation(self):
        """Test AnalysisContext creation."""
        context = AnalysisContext()

        assert context.summary_result is None
        assert context.trends_result is None
        assert context.competition_result == []
        assert context.tools_used == []

    def test_post_init(self):
        """Test AnalysisContext __post_init__ sets defaults."""
        context = AnalysisContext()

        # post_init should have set these
        assert context.competition_result == []
        assert context.tools_used == []


class TestIntelligenceAgent:
    """Tests for IntelligenceAgent class."""

    def test_init_defaults(self, temp_output_dir: Path, monkeypatch):
        """Test IntelligenceAgent initialization."""
        # Mock get_config to return a config with our temp dir
        from dbradar import config as config_module

        mock_config = MagicMock()
        mock_config.output_dir = temp_output_dir
        mock_config.api_key = "test-key"
        mock_config.base_url = "https://api.example.com"
        mock_config.model = "test-model"
        mock_config.language = "en"
        mock_config.timeout = 30.0

        monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

        agent = IntelligenceAgent()

        assert agent.config is not None
        assert agent.summarizer is not None
        assert agent.trend_analyzer is not None
        assert agent.competition_analyzer is not None

    def test_close(self, temp_output_dir: Path, monkeypatch):
        """Test that close properly closes all clients."""
        from dbradar import config as config_module

        mock_config = MagicMock()
        mock_config.output_dir = temp_output_dir
        mock_config.api_key = "test-key"
        mock_config.base_url = "https://api.example.com"
        mock_config.model = "test-model"
        mock_config.language = "en"
        mock_config.timeout = 30.0

        monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

        agent = IntelligenceAgent()
        agent.close()
        assert True

    @patch('dbradar.intelligence.agent.Summarizer')
    def test_analyze_basic_mode(
        self,
        mock_summarizer_class,
        temp_output_dir: Path,
        monkeypatch,
        sample_summary_result,
    ):
        """Test analyze in BASIC mode (core summary only)."""
        from dbradar import config as config_module

        mock_config = MagicMock()
        mock_config.output_dir = temp_output_dir
        mock_config.api_key = "test-key"
        mock_config.base_url = "https://api.example.com"
        mock_config.model = "test-model"
        mock_config.language = "en"
        mock_config.timeout = 30.0

        monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

        # Mock summarizer
        mock_summarizer = MagicMock()
        mock_summarizer.summarize.return_value = sample_summary_result
        mock_summarizer_class.return_value = mock_summarizer

        agent = IntelligenceAgent()
        options = AnalysisOptions(mode=AnalysisMode.BASIC, top_k=10)

        items = [create_mock_ranked_item()]
        report = agent.analyze(items, options)

        assert isinstance(report, IntelligenceReport)
        assert len(report.executive_summary) > 0
        assert "summarize" in report.tools_used
        assert report.trends is None
        assert report.competition == []

    def test_analyze_handles_summary_failure(self, temp_output_dir: Path, monkeypatch):
        """Test analyze handles summarization failure."""
        from dbradar import config as config_module

        mock_config = MagicMock()
        mock_config.output_dir = temp_output_dir
        mock_config.api_key = "test-key"
        mock_config.base_url = "https://api.example.com"
        mock_config.model = "test-model"
        mock_config.language = "en"
        mock_config.timeout = 30.0

        monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

        agent = IntelligenceAgent()

        # Mock summarizer to return error
        with patch.object(agent.summarizer, 'summarize') as mock_summarize:
            mock_result = MagicMock()
            mock_result.executive_summary = ["Error: API failed"]
            mock_summarize.return_value = mock_result

            items = [create_mock_ranked_item()]
            options = AnalysisOptions(mode=AnalysisMode.BASIC)

            report = agent.analyze(items, options)

            assert len(report.executive_summary) == 1
            assert report.executive_summary[0].startswith("Error")


class TestAnalysisOptions:
    """Tests for AnalysisOptions dataclass."""

    def test_defaults(self):
        """Test AnalysisOptions default values."""
        options = AnalysisOptions()

        assert options.mode == AnalysisMode.BASIC
        assert options.top_k == 10
        assert options.history_days == 14
        assert options.enable_trends is False
        assert options.enable_competition is False

    def test_from_mode(self):
        """Test AnalysisOptions.from_mode() factory method."""
        # Test each mode
        basic = AnalysisOptions.from_mode(AnalysisMode.BASIC)
        assert basic.enable_trends is False
        assert basic.enable_competition is False

        trends = AnalysisOptions.from_mode(AnalysisMode.TRENDS)
        assert trends.enable_trends is True
        assert trends.enable_competition is False

        competition = AnalysisOptions.from_mode(AnalysisMode.COMPETITION)
        assert competition.enable_trends is False
        assert competition.enable_competition is True

        intelligence = AnalysisOptions.from_mode(AnalysisMode.INTELLIGENCE)
        assert intelligence.enable_trends is True
        assert intelligence.enable_competition is True


class TestIntelligenceReport:
    """Tests for IntelligenceReport dataclass."""

    def test_creation(self, sample_summary_result):
        """Test IntelligenceReport creation."""
        report = IntelligenceReport(
            executive_summary=sample_summary_result.executive_summary,
            top_updates=sample_summary_result.top_updates,
            release_notes=sample_summary_result.release_notes,
            themes=sample_summary_result.themes,
            action_items=sample_summary_result.action_items,
        )

        assert len(report.executive_summary) == 2
        assert len(report.top_updates) == 3
        assert report.trends is None
        assert report.competition == []

    def test_error_factory(self):
        """Test IntelligenceReport.error() factory method."""
        report = IntelligenceReport.error("Test error message")

        assert len(report.executive_summary) == 1
        assert "Test error message" in report.executive_summary[0]
        assert report.top_updates == []
        assert report.themes == []

    def test_to_dict(
        self,
        sample_summary_result,
        sample_trend_result,
        sample_competitive_insights,
    ):
        """Test IntelligenceReport.to_dict() method."""
        report = IntelligenceReport(
            executive_summary=sample_summary_result.executive_summary,
            top_updates=sample_summary_result.top_updates,
            release_notes=sample_summary_result.release_notes,
            themes=sample_summary_result.themes,
            action_items=sample_summary_result.action_items,
            trends=sample_trend_result,
            competition=sample_competitive_insights,
        )

        data = report.to_dict()

        assert "executive_summary" in data
        assert "top_updates" in data
        assert "intelligence" in data
        assert data["intelligence"]["trends"] is not None
        assert len(data["intelligence"]["competition"]) == 2

    def test_to_dict_without_intelligence(self, sample_summary_result):
        """Test to_dict without intelligence data."""
        report = IntelligenceReport(
            executive_summary=sample_summary_result.executive_summary,
            top_updates=sample_summary_result.top_updates,
            release_notes=sample_summary_result.release_notes,
            themes=sample_summary_result.themes,
            action_items=sample_summary_result.action_items,
        )

        data = report.to_dict()

        assert data["intelligence"] is None


class TestRunIntelligence:
    """Tests for run_intelligence convenience function."""

    def test_run_intelligence_basic(self, monkeypatch):
        """Test run_intelligence with BASIC mode."""
        from dbradar import config as config_module

        mock_config = MagicMock()
        mock_config.output_dir = Path("/tmp/test")
        mock_config.api_key = "test-key"
        mock_config.base_url = "https://api.example.com"
        mock_config.model = "test-model"
        mock_config.language = "en"
        mock_config.timeout = 30.0

        monkeypatch.setattr(config_module, "get_config", lambda: mock_config)

        # Import after patching
        from dbradar.intelligence.agent import run_intelligence

        items = [create_mock_ranked_item()]

        with patch('dbradar.intelligence.agent.IntelligenceAgent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_report = MagicMock()
            mock_report.executive_summary = ["Summary"]
            mock_report.top_updates = []
            mock_report.release_notes = []
            mock_report.themes = []
            mock_report.action_items = []
            mock_agent.analyze.return_value = mock_report
            mock_agent_class.return_value = mock_agent

            result = run_intelligence(items, mode=AnalysisMode.BASIC)

            assert result is not None
            mock_agent.analyze.assert_called_once()
            mock_agent.close.assert_called_once()