"""Base collector module."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class CrawlResult:
    """Web scraping result.

    Attributes:
        success: Whether the crawl was successful.
        data: Crawled data (if successful).
        error: Error message (if failed).
        source: Data source name.
        timestamp: When the crawl occurred.
        metadata: Additional metadata.
    """

    success: bool
    data: Any = None
    error: Optional[str] = None
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any, source: str = "", metadata: dict = None) -> "CrawlResult":
        """Create successful result.

        Args:
            data: Crawled data.
            source: Data source name.
            metadata: Optional metadata.

        Returns:
            CrawlResult instance.
        """
        return cls(
            success=True,
            data=data,
            source=source,
            metadata=metadata or {},
        )

    @classmethod
    def fail(cls, error: str, source: str = "") -> "CrawlResult":
        """Create failed result.

        Args:
            error: Error message.
            source: Data source name.

        Returns:
            CrawlResult instance.
        """
        return cls(
            success=False,
            error=error,
            source=source,
        )


class BaseCollector(ABC):
    """Abstract base class for data collectors.

    Subclasses must implement collect() and validate_params() methods.
    """

    name: str = "base_collector"
    description: str = "Base data collector"

    @abstractmethod
    async def collect(self, **kwargs) -> CrawlResult:
        """Collect data.

        Args:
            **kwargs: Collector-specific parameters.

        Returns:
            CrawlResult with collected data.
        """
        pass

    @abstractmethod
    def validate_params(self, **kwargs) -> bool:
        """Validate input parameters.

        Args:
            **kwargs: Parameters to validate.

        Returns:
            True if parameters are valid.
        """
        pass

    def _format_currency(self, value: float | None, symbol: str = "$") -> str:
        """Format currency value.

        Args:
            value: Numeric value.
            symbol: Currency symbol.

        Returns:
            Formatted currency string.
        """
        if value is None:
            return "N/A"
        return f"{symbol}{value:,.2f}"

    def _format_percent(self, value: float | None) -> str:
        """Format percentage value.

        Args:
            value: Numeric value.

        Returns:
            Formatted percentage string.
        """
        if value is None:
            return "N/A"
        return f"{value:+.2f}%"

    def _format_number(self, value: float | None, decimals: int = 2) -> str:
        """Format numeric value.

        Args:
            value: Numeric value.
            decimals: Number of decimal places.

        Returns:
            Formatted number string.
        """
        if value is None:
            return "N/A"
        return f"{value:,.{decimals}f}"

    def _detect_market(self, stock_code: str) -> str:
        """Detect stock market from code.

        Args:
            stock_code: Stock code to analyze.

        Returns:
            Market identifier: 'CN' (A-share), 'HK' (HK-share), 'US' (US-stock).
        """
        code = stock_code.lower()

        # A-share: starts with sh or sz
        if code.startswith("sh") or code.startswith("sz"):
            return "CN"

        # HK-share: ends with HK or 5-digit number
        if code.endswith("hk") or (code.replace(".", "").isdigit() and len(code) <= 5):
            return "HK"

        # US-stock: alphabetic characters
        if code.isalpha():
            return "US"

        return "UNKNOWN"
