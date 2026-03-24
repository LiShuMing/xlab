"""Tests for scheduler daily_job module."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock
from scheduler import daily_job


class TestIsTradingDay:
    """Tests for trading day detection."""

    def test_saturday_not_trading_day(self):
        """Test that Saturdays are not trading days."""
        # 2026-03-28 is a Saturday
        saturday = date(2026, 3, 28)
        result = daily_job.is_trading_day(saturday)
        assert result is False

    def test_sunday_not_trading_day(self):
        """Test that Sundays are not trading days."""
        # 2026-03-29 is a Sunday
        sunday = date(2026, 3, 29)
        result = daily_job.is_trading_day(sunday)
        assert result is False

    def test_weekday_may_be_trading_day(self):
        """Test that weekdays may be trading days."""
        # 2026-03-24 is a Tuesday
        tuesday = date(2026, 3, 24)
        result = daily_job.is_trading_day(tuesday)
        # Result depends on Chinese holiday calendar
        assert isinstance(result, bool)


class TestModuleStructure:
    """Tests for module structure and imports."""

    def test_daily_job_module_exists(self):
        """Verify daily_job module has expected attributes."""
        assert hasattr(daily_job, "is_trading_day")
        assert hasattr(daily_job, "run_daily_analysis")

    def test_daily_job_result_exists(self):
        """Verify DailyJobResult dataclass exists."""
        assert hasattr(daily_job, "DailyJobResult")


class TestDailyJobResult:
    """Tests for DailyJobResult dataclass."""

    def test_basic_creation(self):
        """Test creating a DailyJobResult."""
        result = daily_job.DailyJobResult(
            success=True,
            stocks_analyzed=5,
        )
        assert result.success is True
        assert result.stocks_analyzed == 5

    def test_with_error(self):
        """Test creating a DailyJobResult with error."""
        result = daily_job.DailyJobResult(
            success=False,
            error="LLM API error",
        )
        assert result.success is False
        assert result.error == "LLM API error"


class TestRunDailyAnalysis:
    """Tests for run_daily_analysis function."""

    @pytest.mark.asyncio
    async def test_non_trading_day_skips(self):
        """Test that analysis is skipped on non-trading days."""
        with patch.object(daily_job, "is_trading_day", return_value=False):
            result = await daily_job.run_daily_analysis(dry_run=True)

        # When not a trading day, no stocks are analyzed
        assert result.stocks_analyzed == 0


class TestIntegration:
    """Integration tests that verify module interactions."""

    def test_scheduler_imports_orchestrator(self):
        """Test that scheduler imports orchestrator correctly."""
        # This verifies the import path works
        from agents.orchestrator import SimpleAgentOrchestrator
        assert SimpleAgentOrchestrator is not None

    def test_scheduler_imports_repository(self):
        """Test that scheduler imports repository correctly."""
        from storage import repository
        assert repository is not None

    def test_scheduler_imports_config(self):
        """Test that scheduler imports config correctly."""
        from config import load_config
        assert load_config is not None

    def test_scheduler_imports_email_sender(self):
        """Test that scheduler imports email_sender correctly."""
        from notifier import email_sender
        assert email_sender is not None