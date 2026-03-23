"""Report type definitions."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class ReportFormat(str, Enum):
    """Report output format.

    Values:
        MARKDOWN: Markdown format.
        HTML: HTML format.
        JSON: JSON format.
    """

    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


@dataclass
class ReportSection:
    """Report section.

    Attributes:
        title: Section title.
        content: Section content.
        order: Display order.
        metadata: Additional metadata.
    """

    title: str
    content: str
    order: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class Report:
    """Investment analysis report.

    Attributes:
        stock_code: Stock ticker symbol.
        stock_name: Company name.
        report_id: Unique report identifier.
        title: Report title.
        summary: Executive summary.
        sections: Report sections.
        rating: Investment rating.
        confidence: Confidence level.
        target_price: Target price.
        bull_case: Bull case scenario analysis.
        bear_case: Bear case scenario analysis.
        base_case: Base case scenario analysis.
        created_at: Creation timestamp.
        model_name: LLM model used.
        analysis_duration: Analysis duration in seconds.
        raw_data: Raw data used for analysis.
    """

    stock_code: str
    stock_name: str = ""
    report_id: str = ""

    title: str = ""
    summary: str = ""
    sections: list[ReportSection] = field(default_factory=list)

    rating: str = ""
    confidence: str = ""
    target_price: Optional[float] = None

    bull_case: Optional[str] = None
    bear_case: Optional[str] = None
    base_case: Optional[str] = None

    created_at: datetime = field(default_factory=datetime.now)
    model_name: str = ""
    analysis_duration: float = 0.0

    raw_data: dict = field(default_factory=dict)

    def add_section(self, title: str, content: str, order: int = 0) -> "Report":
        """Add a section to the report.

        Args:
            title: Section title.
            content: Section content.
            order: Display order.

        Returns:
            Self for method chaining.
        """
        self.sections.append(
            ReportSection(
                title=title,
                content=content,
                order=order or len(self.sections),
            )
        )
        return self

    def get_section(self, title: str) -> Optional[ReportSection]:
        """Get section by title.

        Args:
            title: Section title.

        Returns:
            ReportSection or None if not found.
        """
        for section in self.sections:
            if section.title == title:
                return section
        return None

    def sort_sections(self) -> "Report":
        """Sort sections by order.

        Returns:
            Self for method chaining.
        """
        self.sections.sort(key=lambda s: s.order)
        return self
