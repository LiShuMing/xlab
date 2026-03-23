"""
Utilities module for AI Lab Platform.

Provides logging, UI helpers, and output formatting utilities.
"""

from utils.logger import get_logger, configure_logging
from utils.output import (
    Report,
    ReportMetadata,
    ReportSection,
    ReportFormat,
    create_stock_report,
    quick_output,
)

# UI helpers require streamlit, import separately
__all__ = [
    # Logger
    "get_logger",
    "configure_logging",
    # Output
    "Report",
    "ReportMetadata",
    "ReportSection",
    "ReportFormat",
    "create_stock_report",
    "quick_output",
]

# Optional imports that require streamlit
try:
    from utils.ui_helpers import (
        render_sidebar_header,
        render_footer,
        render_info_box,
        render_metric_row,
        InfoBoxType,
    )
    __all__.extend([
        "render_sidebar_header",
        "render_footer",
        "render_info_box",
        "render_metric_row",
        "InfoBoxType",
    ])
except ImportError:
    # Streamlit not available (e.g., in tests)
    pass
