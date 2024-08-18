"""Diff module for incremental report comparison.

This module provides functionality to compare daily stock analysis reports
and detect significant changes that should be highlighted in email notifications.
"""

from .comparator import Change, IncrementalReport, compare_reports
from .formatter import format_incremental_email, format_single_stock, format_change, format_email_subject

__all__ = [
    "Change",
    "IncrementalReport",
    "compare_reports",
    "format_incremental_email",
    "format_single_stock",
    "format_change",
    "format_email_subject",
]