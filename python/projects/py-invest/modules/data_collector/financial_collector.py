"""Financial data collector using yfinance."""

import yfinance as yf
from datetime import datetime
from typing import Optional, Any

from .base import BaseCollector, CrawlResult


class FinancialCollector(BaseCollector):
    """Financial metrics collector using yfinance.

    Collects valuation, profitability, growth, and financial health metrics.
    """

    name = "financial_collector"
    description = "Collect stock financial metrics and ratios"

    def __init__(self, timeout: int = 30):
        """Initialize financial collector.

        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout

    def validate_params(self, stock_code: str, **kwargs) -> bool:
        """Validate stock code parameter.

        Args:
            stock_code: Stock code.

        Returns:
            True if stock code is provided.
        """
        return bool(stock_code)

    async def collect(
        self,
        stock_code: str,
        report_type: str = "all",
        **kwargs,
    ) -> CrawlResult:
        """Collect financial data.

        Args:
            stock_code: Stock code.
            report_type: Report type (all/income/balance/cashflow).

        Returns:
            CrawlResult with financial data.
        """
        try:
            ticker = self._convert_ticker(stock_code)
            info = yf.Ticker(ticker).info

            if not info:
                return CrawlResult.fail("No financial data received", source=self.name)

            financial_data = self._parse_financials(info, stock_code)
            return CrawlResult.ok(financial_data, source=self.name)

        except Exception as e:
            return CrawlResult.fail(str(e), source=self.name)

    def _convert_ticker(self, stock_code: str) -> str:
        """Convert stock code to yfinance ticker format.

        Args:
            stock_code: Stock code.

        Returns:
            yfinance ticker symbol.
        """
        code = stock_code.upper()

        if code.startswith("SH"):
            return f"{code[2:]}.SS"
        elif code.startswith("SZ"):
            return f"{code[2:]}.SZ"
        if ".HK" in code:
            return code
        return code

    def _parse_financials(self, info: dict, stock_code: str) -> dict:
        """Parse financial metrics from yfinance info.

        Args:
            info: yfinance info dictionary.
            stock_code: Stock code.

        Returns:
            Parsed financial metrics dictionary.
        """
        return {
            "stock_code": stock_code,
            "market_cap": self._safe_get(info, "marketCap"),
            "enterprise_value": self._safe_get(info, "enterpriseValue"),
            "trailing_pe": self._safe_get(info, "trailingPE"),
            "forward_pe": self._safe_get(info, "forwardPE"),
            "price_to_book": self._safe_get(info, "priceToBook"),
            "price_to_sales": self._safe_get(info, "priceToSalesTrailing12Months"),
            "ev_to_revenue": self._safe_get(info, "enterpriseToRevenue"),
            "ev_to_ebitda": self._safe_get(info, "enterpriseToEbitda"),
            "profit_margin": self._safe_get(info, "profitMargins"),
            "operating_margin": self._safe_get(info, "operatingMargins"),
            "return_on_equity": self._safe_get(info, "returnOnEquity"),
            "return_on_assets": self._safe_get(info, "returnOnAssets"),
            "debt_to_equity": self._safe_get(info, "debtToEquity"),
            "current_ratio": self._safe_get(info, "currentRatio"),
            "quick_ratio": self._safe_get(info, "quickRatio"),
            "revenue_growth": self._safe_get(info, "revenueGrowth"),
            "earnings_growth": self._safe_get(info, "earningsGrowth"),
            "book_value": self._safe_get(info, "bookValue"),
            "operating_cashflow": self._safe_get(info, "operatingCashflow"),
            "free_cashflow": self._safe_get(info, "freeCashflow"),
            "dividend_yield": self._safe_get(info, "dividendYield"),
            "payout_ratio": self._safe_get(info, "payoutRatio"),
            "beta": self._safe_get(info, "beta"),
            "52_week_high": self._safe_get(info, "fiftyTwoWeekHigh"),
            "52_week_low": self._safe_get(info, "fiftyTwoWeekLow"),
            "timestamp": datetime.now(),
        }

    def _safe_get(self, data: dict, key: str) -> Optional[Any]:
        """Safely get value from dictionary.

        Args:
            data: Source dictionary.
            key: Key to lookup.

        Returns:
            Value or None if not found or invalid.
        """
        value = data.get(key)
        if value is None or value == "N/A":
            return None
        return value

    def format_markdown(self, data: dict) -> str:
        """Format financial data as Markdown tables.

        Args:
            data: Financial data dictionary.

        Returns:
            Markdown formatted tables.
        """
        md = """## Financial Metrics

### Valuation Ratios
| Metric | Value |
|--------|-------|
"""
        md += f"| Market Cap | {self._format_valuation(data.get('market_cap'))} |\n"
        md += f"| Enterprise Value | {self._format_valuation(data.get('enterprise_value'))} |\n"
        md += f"| P/E Ratio (TTM) | {self._format_number(data.get('trailing_pe'))} |\n"
        md += f"| P/B Ratio | {self._format_number(data.get('price_to_book'))} |\n"
        md += f"| P/S Ratio | {self._format_number(data.get('price_to_sales'))} |\n"

        md += """
### Profitability Metrics
| Metric | Value |
|--------|-------|
"""
        md += f"| Net Profit Margin | {self._format_percent(data.get('profit_margin'))} |\n"
        md += f"| Operating Margin | {self._format_percent(data.get('operating_margin'))} |\n"
        md += f"| Return on Equity | {self._format_percent(data.get('return_on_equity'))} |\n"
        md += f"| Return on Assets | {self._format_percent(data.get('return_on_assets'))} |\n"

        md += """
### Growth Metrics
| Metric | Value |
|--------|-------|
"""
        md += f"| Revenue Growth | {self._format_percent(data.get('revenue_growth'))} |\n"
        md += f"| Earnings Growth | {self._format_percent(data.get('earnings_growth'))} |\n"

        md += """
### Financial Health
| Metric | Value |
|--------|-------|
"""
        md += f"| Debt-to-Equity | {self._format_number(data.get('debt_to_equity'))} |\n"
        md += f"| Current Ratio | {self._format_number(data.get('current_ratio'))} |\n"
        md += f"| Quick Ratio | {self._format_number(data.get('quick_ratio'))} |\n"

        return md

    def _format_valuation(self, value: Optional[float]) -> str:
        """Format valuation value.

        Args:
            value: Numeric value.

        Returns:
            Formatted string with B/M suffix.
        """
        if value is None:
            return "N/A"
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        return f"{value:.2f}"
