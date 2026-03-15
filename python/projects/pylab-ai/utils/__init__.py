"""Utilities module for AI Lab Platform."""

from .logger import get_logger
from .ui_helpers import render_sidebar_header, render_footer

# Output layer components (for convenient imports)
from .output import (
    Report,
    ReportFormat,
    ReportSection,
    ReportMetadata,
    quick_output,
    create_stock_report,
    BaseRenderer,
    BaseDispatcher,
    OutputManager,
)

__all__ = [
    "get_logger", 
    "render_sidebar_header", 
    "render_footer",
    # Output layer
    "Report",
    "ReportFormat",
    "ReportSection",
    "ReportMetadata",
    "quick_output",
    "create_stock_report",
    "BaseRenderer",
    "BaseDispatcher",
    "OutputManager",
]
