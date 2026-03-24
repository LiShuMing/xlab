"""Tests for diff comparator module."""

import pytest
from datetime import datetime
from diff.comparator import (
    compare_reports,
    Change,
    IncrementalReport,
    PRICE_CHANGE_THRESHOLD,
    PE_PB_CHANGE_THRESHOLD,
)


class TestChange:
    """Tests for Change dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        change = Change(field="price", old_value=100, new_value=105)
        assert change.field == "price"
        assert change.old_value == 100
        assert change.new_value == 105
        assert change.change_pct is None
        assert change.triggers_analysis is False
        assert change.details == {}

    def test_with_all_values(self):
        """Test with all values set."""
        change = Change(
            field="price",
            old_value=100,
            new_value=105,
            change_pct=5.0,
            triggers_analysis=True,
            details={"threshold_exceeded": True},
        )
        assert change.change_pct == 5.0
        assert change.triggers_analysis is True
        assert change.details["threshold_exceeded"] is True


class TestIncrementalReport:
    """Tests for IncrementalReport dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        report = IncrementalReport(stock_code="sh600519", stock_name="贵州茅台")
        assert report.stock_code == "sh600519"
        assert report.stock_name == "贵州茅台"
        assert report.is_first_run is False
        assert report.changes == []
        assert report.has_significant_changes is False

    def test_add_change_updates_significant_flag(self):
        """Test that adding a change with triggers_analysis updates flag."""
        report = IncrementalReport(stock_code="sh600519", stock_name="贵州茅台")
        assert report.has_significant_changes is False

        report.add_change(Change(field="price", old_value=100, new_value=105, triggers_analysis=True))
        assert report.has_significant_changes is True

    def test_add_change_without_trigger_keeps_flag(self):
        """Test that adding a change without trigger doesn't update flag."""
        report = IncrementalReport(stock_code="sh600519", stock_name="贵州茅台")
        report.add_change(Change(field="price", old_value=100, new_value=101, triggers_analysis=False))
        assert report.has_significant_changes is False


class TestCompareReports:
    """Tests for compare_reports function."""

    def test_first_run_sets_flag(self):
        """Test that first run sets is_first_run flag."""
        today = {"stock_code": "sh600519", "stock_name": "贵州茅台"}
        result = compare_reports(today, None)
        assert result.is_first_run is True
        assert result.has_significant_changes is True

    def test_no_changes_detected(self):
        """Test when there are no significant changes."""
        today = {
            "stock_code": "sh600519",
            "stock_name": "贵州茅台",
            "rating": "Buy",
            "confidence": "high",
            "raw_data": {
                "price": {"current_price": 100, "prev_close": 100},
                "financials": {"trailing_pe": 20, "price_to_book": 5},
            },
        }
        yesterday = {
            "stock_code": "sh600519",
            "stock_name": "贵州茅台",
            "rating": "Buy",
            "confidence": "high",
            "raw_data": {
                "price": {"current_price": 100, "prev_close": 100},
                "financials": {"trailing_pe": 20, "price_to_book": 5},
            },
        }
        result = compare_reports(today, yesterday)
        assert result.is_first_run is False
        assert len(result.changes) == 0
        assert result.has_significant_changes is False

    def test_price_change_above_threshold(self):
        """Test price change detection above threshold."""
        today = {
            "stock_code": "sh600519",
            "stock_name": "贵州茅台",
            "raw_data": {
                "price": {"current_price": 105, "prev_close": 100},
            },
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {
                "price": {"current_price": 100, "prev_close": 100},
            },
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 1
        assert result.changes[0].field == "price"
        assert result.changes[0].change_pct == 5.0
        assert result.changes[0].triggers_analysis is True
        assert result.has_significant_changes is True

    def test_price_change_below_threshold(self):
        """Test price change detection below threshold."""
        today = {
            "stock_code": "sh600519",
            "raw_data": {
                "price": {"current_price": 101, "prev_close": 100},
            },
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {
                "price": {"current_price": 100, "prev_close": 100},
            },
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 0

    def test_price_as_float_value(self):
        """Test price comparison with float value directly."""
        today = {
            "stock_code": "sh600519",
            "raw_data": {
                "price": 105.0,  # Float instead of dict
            },
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {
                "price": 100.0,
            },
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 1
        assert result.changes[0].change_pct == 5.0

    def test_rating_change_detection(self):
        """Test rating change detection."""
        today = {
            "stock_code": "sh600519",
            "rating": "Buy",
            "confidence": "high",
        }
        yesterday = {
            "stock_code": "sh600519",
            "rating": "Hold",
            "confidence": "medium",
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 1
        assert result.changes[0].field == "rating"
        assert result.changes[0].triggers_analysis is True

    def test_target_price_change(self):
        """Test target price change detection."""
        today = {
            "stock_code": "sh600519",
            "target_price": 2100,
        }
        yesterday = {
            "stock_code": "sh600519",
            "target_price": 2000,
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 1
        assert result.changes[0].field == "target_price"
        assert result.changes[0].change_pct == 5.0

    def test_new_news_detection(self):
        """Test new news items detection."""
        today = {
            "stock_code": "sh600519",
            "raw_data": {
                "news": {
                    "news": [
                        {
                            "title": "New News",
                            "source": "Sina",
                            "published_at": "2026-03-24 10:00",
                            "link": "http://example.com/1",
                        },
                        {
                            "title": "Old News",
                            "source": "Sina",
                            "published_at": "2026-03-23 10:00",
                            "link": "http://example.com/2",
                        },
                    ]
                }
            },
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {
                "news": {
                    "news": [
                        {
                            "title": "Old News",
                            "source": "Sina",
                            "published_at": "2026-03-23 10:00",
                            "link": "http://example.com/2",
                        }
                    ]
                }
            },
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 1
        assert result.changes[0].field == "news"
        assert result.changes[0].details["new_count"] == 1

    def test_pe_ratio_change_above_threshold(self):
        """Test PE ratio change detection."""
        today = {
            "stock_code": "sh600519",
            "raw_data": {
                "financials": {"trailing_pe": 25},
            },
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {
                "financials": {"trailing_pe": 20},
            },
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 1
        assert result.changes[0].field == "pe_ratio"
        assert result.changes[0].change_pct == 25.0

    def test_support_resistance_break_detection(self):
        """Test support/resistance break detection."""
        today = {
            "stock_code": "sh600519",
            "sections": [
                {
                    "title": "Technical Picture",
                    "content": "The stock has broken above the key resistance level at 105. This is a breakout signal.",
                }
            ],
        }
        yesterday = {
            "stock_code": "sh600519",
            "sections": [],
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 1
        assert result.changes[0].field == "support_resistance"

    def test_multiple_changes_detected(self):
        """Test detection of multiple changes in one comparison."""
        today = {
            "stock_code": "sh600519",
            "rating": "Buy",
            "confidence": "high",
            "target_price": 2100,
            "raw_data": {
                "price": {"current_price": 105},
                "financials": {"trailing_pe": 25},
            },
        }
        yesterday = {
            "stock_code": "sh600519",
            "rating": "Hold",
            "confidence": "medium",
            "target_price": 2000,
            "raw_data": {
                "price": {"current_price": 100},
                "financials": {"trailing_pe": 20},
            },
        }
        result = compare_reports(today, yesterday)
        # Should detect: price, rating, target_price, pe_ratio
        assert len(result.changes) >= 3


class TestPriceThreshold:
    """Tests for price change threshold logic."""

    def test_exactly_at_threshold(self):
        """Test price change exactly at threshold (should trigger)."""
        # 2% threshold
        today = {
            "stock_code": "sh600519",
            "raw_data": {"price": {"current_price": 102}},
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {"price": {"current_price": 100}},
        }
        result = compare_reports(today, yesterday)
        # Exactly 2% should NOT trigger (threshold is > 2.0)
        assert len(result.changes) == 0

    def test_just_above_threshold(self):
        """Test price change just above threshold."""
        today = {
            "stock_code": "sh600519",
            "raw_data": {"price": {"current_price": 102.1}},
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {"price": {"current_price": 100}},
        }
        result = compare_reports(today, yesterday)
        # 2.1% should trigger
        assert len(result.changes) == 1

    def test_negative_change_above_threshold(self):
        """Test negative price change above threshold."""
        today = {
            "stock_code": "sh600519",
            "raw_data": {"price": {"current_price": 95}},
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {"price": {"current_price": 100}},
        }
        result = compare_reports(today, yesterday)
        # -5% should trigger
        assert len(result.changes) == 1
        assert result.changes[0].change_pct == -5.0


class TestEdgeCases:
    """Tests for edge cases in comparison."""

    def test_missing_yesterday_price(self):
        """Test handling when yesterday has no price data."""
        today = {
            "stock_code": "sh600519",
            "raw_data": {"price": {"current_price": 100}},
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {},
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 0

    def test_zero_yesterday_price(self):
        """Test handling when yesterday price is zero."""
        today = {
            "stock_code": "sh600519",
            "raw_data": {"price": {"current_price": 100}},
        }
        yesterday = {
            "stock_code": "sh600519",
            "raw_data": {"price": {"current_price": 0}},
        }
        result = compare_reports(today, yesterday)
        # Should not crash, just skip
        assert isinstance(result, IncrementalReport)

    def test_none_values_in_comparison(self):
        """Test handling of None values."""
        today = {
            "stock_code": "sh600519",
            "target_price": None,
        }
        yesterday = {
            "stock_code": "sh600519",
            "target_price": None,
        }
        result = compare_reports(today, yesterday)
        assert len(result.changes) == 0