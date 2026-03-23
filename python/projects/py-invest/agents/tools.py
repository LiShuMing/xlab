"""Agent tool implementations."""

from typing import Any

from .base import BaseAgentTool, ToolInfo, ToolParameter, ToolResult
from modules.data_collector import (
    PriceCollector,
    KLineCollector,
    FinancialCollector,
    NewsCollector,
)


class QueryStockPriceTool(BaseAgentTool):
    """Tool for querying real-time stock prices."""

    name = "query_stock_price"
    description = "Query stock real-time price"

    def __init__(self):
        """Initialize price query tool."""
        self._collector = PriceCollector()

    def get_info(self) -> ToolInfo:
        """Get tool information."""
        return ToolInfo(
            name=self.name,
            description="Get real-time stock price, change percent, volume, and market cap",
            parameters=[
                ToolParameter(
                    name="stock_code",
                    type="string",
                    description="Stock code, e.g., sh600519 (Moutai), sz000001 (Ping An), AAPL",
                    required=True,
                ),
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        """Execute price query.

        Args:
            arguments: Tool arguments with stock_code.

        Returns:
            Formatted price data or error message.
        """
        stock_code = arguments.get("stock_code", "")
        if not stock_code:
            return ToolResult.fail("Stock code is required", self.name).result

        result = await self._collector.collect(stock_code=stock_code)
        if result.success:
            return self._collector.format_markdown(result.data)
        return ToolResult.fail(result.error or "Failed to fetch data", self.name).result


class QueryKLineDataTool(BaseAgentTool):
    """Tool for querying K-line (candlestick) data."""

    name = "query_kline_data"
    description = "Query stock K-line data"

    def __init__(self):
        """Initialize K-line query tool."""
        self._collector = KLineCollector()

    def get_info(self) -> ToolInfo:
        """Get tool information."""
        return ToolInfo(
            name=self.name,
            description="Get historical K-line data including open, high, low, close, and volume",
            parameters=[
                ToolParameter(
                    name="stock_code",
                    type="string",
                    description="Stock code",
                    required=True,
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="Number of days to fetch (default: 90, max: 365)",
                    required=False,
                    default=90,
                ),
                ToolParameter(
                    name="period",
                    type="string",
                    description="Period type: day, week, month",
                    required=False,
                    default="day",
                    enum=["day", "week", "month"],
                ),
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        """Execute K-line query.

        Args:
            arguments: Tool arguments.

        Returns:
            Formatted K-line data or error message.
        """
        stock_code = arguments.get("stock_code", "")
        days = arguments.get("days", 90)
        period = arguments.get("period", "day")

        result = await self._collector.collect(stock_code=stock_code, days=days, period=period)
        if result.success:
            return self._collector.format_markdown(result.data)
        return ToolResult.fail(result.error or "Failed to fetch data", self.name).result


class QueryFinancialMetricsTool(BaseAgentTool):
    """Tool for querying financial metrics."""

    name = "query_financial_metrics"
    description = "Query stock financial metrics"

    def __init__(self):
        """Initialize financial metrics query tool."""
        self._collector = FinancialCollector()

    def get_info(self) -> ToolInfo:
        """Get tool information."""
        return ToolInfo(
            name=self.name,
            description="Get financial metrics including valuation, profitability, growth, and financial health",
            parameters=[
                ToolParameter(
                    name="stock_code",
                    type="string",
                    description="Stock code",
                    required=True,
                ),
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        """Execute financial metrics query.

        Args:
            arguments: Tool arguments with stock_code.

        Returns:
            Formatted financial data or error message.
        """
        stock_code = arguments.get("stock_code", "")
        if not stock_code:
            return ToolResult.fail("Stock code is required", self.name).result

        result = await self._collector.collect(stock_code=stock_code)
        if result.success:
            return self._collector.format_markdown(result.data)
        return ToolResult.fail(result.error or "Failed to fetch data", self.name).result


class QueryMarketNewsTool(BaseAgentTool):
    """Tool for querying market news."""

    name = "query_market_news"
    description = "Query market news"

    def __init__(self):
        """Initialize news query tool."""
        self._collector = NewsCollector()

    def get_info(self) -> ToolInfo:
        """Get tool information."""
        return ToolInfo(
            name=self.name,
            description="Get market news and financial information, support stock-specific or macro news",
            parameters=[
                ToolParameter(
                    name="stock_code",
                    type="string",
                    description="Stock code (optional, fetches macro news if not provided)",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Number of news items (default: 20)",
                    required=False,
                    default=20,
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="Number of days to look back (default: 7)",
                    required=False,
                    default=7,
                ),
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        """Execute news query.

        Args:
            arguments: Tool arguments.

        Returns:
            Formatted news data or error message.
        """
        stock_code = arguments.get("stock_code")
        limit = arguments.get("limit", 20)
        days = arguments.get("days", 7)

        result = await self._collector.collect(stock_code=stock_code, limit=limit, days=days)
        if result.success:
            return self._collector.format_markdown(result.data)
        return ToolResult.fail(result.error or "Failed to fetch data", self.name).result
