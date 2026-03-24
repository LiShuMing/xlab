"""Tests for storage repository module.

Note: These tests focus on verifying the module structure and import paths.
Integration tests with a real database are done via the --dry-run CLI test.
"""

import pytest
import json
from datetime import date
from unittest.mock import patch, MagicMock

# Test that the module imports correctly
from storage.models import (
    DailyReport,
    StockConfig,
    PendingEmail,
    EmailLog,
    get_db_path,
    init_db,
)
import storage.repository as repo


class TestModuleStructure:
    """Tests for module structure and imports."""

    def test_repository_functions_exist(self):
        """Verify all expected repository functions exist."""
        assert hasattr(repo, "save_report")
        assert hasattr(repo, "get_report")
        assert hasattr(repo, "get_latest_report")
        assert hasattr(repo, "get_reports_for_date")
        assert hasattr(repo, "sync_stock_configs")
        assert hasattr(repo, "get_active_stocks")
        assert hasattr(repo, "save_pending_email")
        assert hasattr(repo, "get_pending_emails")
        assert hasattr(repo, "delete_pending_email")
        assert hasattr(repo, "increment_retry_count")
        assert hasattr(repo, "log_email")
        assert hasattr(repo, "get_recent_email_logs")

    def test_db_path_is_in_home_directory(self):
        """Test that database path is in user's home directory."""
        db_path = get_db_path()
        assert ".py-invest" in str(db_path)
        assert db_path.name == "data.db"


class TestDataclasses:
    """Tests for dataclass factory methods."""

    def test_daily_report_from_row(self):
        """Test DailyReport.from_row factory method."""
        row = (1, "sh600519", "2026-03-24", '{"rating": "Buy"}', "2026-03-24 10:00:00")
        report = DailyReport.from_row(row)
        assert report.id == 1
        assert report.stock_code == "sh600519"
        assert report.analysis_json == '{"rating": "Buy"}'

    def test_daily_report_from_row_with_date_obj(self):
        """Test DailyReport.from_row with date object."""
        row = (1, "sh600519", date(2026, 3, 24), '{"rating": "Buy"}', None)
        report = DailyReport.from_row(row)
        assert report.report_date == date(2026, 3, 24)

    def test_stock_config_from_row(self):
        """Test StockConfig.from_row factory method."""
        row = ("sh600519", "贵州茅台", 1, "2026-03-24 10:00:00")
        config = StockConfig.from_row(row)
        assert config.stock_code == "sh600519"
        assert config.stock_name == "贵州茅台"
        assert config.is_active is True

    def test_stock_config_from_row_inactive(self):
        """Test StockConfig.from_row with inactive flag."""
        row = ("sh600519", "贵州茅台", 0, None)
        config = StockConfig.from_row(row)
        assert config.is_active is False

    def test_pending_email_from_row(self):
        """Test PendingEmail.from_row factory method."""
        row = (1, "2026-03-24 10:00:00", "test@example.com", "Test Subject", "Test Body", 2)
        email = PendingEmail.from_row(row)
        assert email.id == 1
        assert email.recipient == "test@example.com"
        assert email.retry_count == 2

    def test_email_log_from_row(self):
        """Test EmailLog.from_row factory method."""
        row = (1, "2026-03-24 10:00:00", "test@example.com", "Test", 5, "success", None)
        log = EmailLog.from_row(row)
        assert log.id == 1
        assert log.stock_count == 5
        assert log.status == "success"


class TestRepositoryFunctionSignatures:
    """Tests for repository function signatures."""

    def test_save_report_signature(self):
        """Test save_report accepts correct parameters."""
        import inspect
        sig = inspect.signature(repo.save_report)
        params = list(sig.parameters.keys())
        assert "stock_code" in params
        assert "report_date" in params
        assert "analysis_json" in params

    def test_get_report_signature(self):
        """Test get_report accepts correct parameters."""
        import inspect
        sig = inspect.signature(repo.get_report)
        params = list(sig.parameters.keys())
        assert "stock_code" in params
        assert "report_date" in params

    def test_sync_stock_configs_signature(self):
        """Test sync_stock_configs accepts correct parameters."""
        import inspect
        sig = inspect.signature(repo.sync_stock_configs)
        params = list(sig.parameters.keys())
        assert "stocks" in params

    def test_get_pending_emails_signature(self):
        """Test get_pending_emails accepts max_retries parameter."""
        import inspect
        sig = inspect.signature(repo.get_pending_emails)
        params = list(sig.parameters.keys())
        assert "max_retries" in params

    def test_log_email_signature(self):
        """Test log_email accepts correct parameters."""
        import inspect
        sig = inspect.signature(repo.log_email)
        params = list(sig.parameters.keys())
        assert "recipient" in params
        assert "subject" in params
        assert "stock_count" in params
        assert "status" in params
        assert "error_message" in params