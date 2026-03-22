"""Report builder with fluent interface."""

import uuid
from datetime import datetime
from typing import Optional

from .types import Report, ReportSection


class ReportBuilder:
    """Fluent builder for constructing investment reports.

    Example:
        >>> report = (ReportBuilder()
        ...     .set_stock("sh600519", "Kweichow Moutai")
        ...     .set_title("Investment Analysis Report")
        ...     .add_section("Overview", "Company overview...")
        ...     .set_rating("Strong Buy", "High")
        ...     .build())
    """

    def __init__(self):
        """Initialize report builder."""
        self._report = Report(report_id=str(uuid.uuid4())[:8])
        self._section_order = 0

    def set_stock(self, stock_code: str, stock_name: str = "") -> "ReportBuilder":
        """Set stock information.

        Args:
            stock_code: Stock ticker symbol.
            stock_name: Company name.

        Returns:
            Self for method chaining.
        """
        self._report.stock_code = stock_code
        self._report.stock_name = stock_name
        return self

    def set_title(self, title: str) -> "ReportBuilder":
        """Set report title.

        Args:
            title: Report title.

        Returns:
            Self for method chaining.
        """
        self._report.title = title
        return self

    def set_summary(self, summary: str) -> "ReportBuilder":
        """Set executive summary.

        Args:
            summary: Summary text.

        Returns:
            Self for method chaining.
        """
        self._report.summary = summary
        return self

    def set_rating(self, rating: str, confidence: str = "") -> "ReportBuilder":
        """Set investment rating.

        Args:
            rating: Rating (e.g., "Strong Buy", "Buy", "Hold").
            confidence: Confidence level.

        Returns:
            Self for method chaining.
        """
        self._report.rating = rating
        self._report.confidence = confidence
        return self

    def set_target_price(self, price: float) -> "ReportBuilder":
        """Set target price.

        Args:
            price: Target price value.

        Returns:
            Self for method chaining.
        """
        self._report.target_price = price
        return self

    def add_section(
        self,
        title: str,
        content: str,
        order: Optional[int] = None,
    ) -> "ReportBuilder":
        """Add a section to the report.

        Args:
            title: Section title.
            content: Section content.
            order: Display order (auto-incremented if not provided).

        Returns:
            Self for method chaining.
        """
        self._report.sections.append(
            ReportSection(
                title=title,
                content=content,
                order=order if order is not None else self._section_order,
            )
        )
        self._section_order += 1
        return self

    def set_model(self, model_name: str) -> "ReportBuilder":
        """Set LLM model information.

        Args:
            model_name: Model name used for analysis.

        Returns:
            Self for method chaining.
        """
        self._report.model_name = model_name
        return self

    def set_duration(self, duration: float) -> "ReportBuilder":
        """Set analysis duration.

        Args:
            duration: Duration in seconds.

        Returns:
            Self for method chaining.
        """
        self._report.analysis_duration = duration
        return self

    def set_raw_data(self, raw_data: dict) -> "ReportBuilder":
        """Set raw data used for analysis.

        Args:
            raw_data: Raw data dictionary.

        Returns:
            Self for method chaining.
        """
        self._report.raw_data = raw_data
        return self

    def build(self) -> Report:
        """Build and return the report.

        Returns:
            Completed Report instance.
        """
        self._report.sort_sections()
        return self._report

    def reset(self) -> "ReportBuilder":
        """Reset builder to initial state.

        Returns:
            Self for method chaining.
        """
        self._report = Report(report_id=str(uuid.uuid4())[:8])
        self._section_order = 0
        return self
