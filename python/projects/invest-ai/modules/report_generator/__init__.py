"""报告生成模块 - 结构化报告构建"""

__version__ = "0.1.0"

from .types import Report, ReportSection, ReportFormat
from .builder import ReportBuilder
from .formatter import ReportFormatter

__all__ = [
    "Report",
    "ReportSection",
    "ReportFormat",
    "ReportBuilder",
    "ReportFormatter",
]
