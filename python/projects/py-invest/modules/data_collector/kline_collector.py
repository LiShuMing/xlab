"""K-line (candlestick) data collector using yfinance."""

import yfinance as yf
from datetime import datetime
from typing import Optional

from .base import BaseCollector, CrawlResult

# pandas dependency
try:
    import pandas as pd
except ImportError:
    pd = None


class KLineCollector(BaseCollector):
    """K-line data collector using yfinance.

    Supports daily, weekly, and monthly candlestick data.
    """

    name = "kline_collector"
    description = "Collect stock K-line (OHLCV) data"

    def __init__(self, timeout: int = 30):
        """Initialize K-line collector.

        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout

    def validate_params(self, stock_code: str, days: int = 90, **kwargs) -> bool:
        """Validate parameters.

        Args:
            stock_code: Stock code.
            days: Number of days to fetch.

        Returns:
            True if parameters are valid.
        """
        if not stock_code:
            return False
        if not isinstance(days, int) or days < 1 or days > 365:
            return False
        return True

    async def collect(
        self,
        stock_code: str,
        days: int = 90,
        period: str = "day",
        **kwargs,
    ) -> CrawlResult:
        """Collect K-line data.

        Args:
            stock_code: Stock code.
            days: Number of days to fetch.
            period: Period type (day/week/month).

        Returns:
            CrawlResult with K-line data.
        """
        try:
            ticker = self._convert_ticker(stock_code)
            data = yf.download(ticker, period=f"{days}d", interval=self._get_interval(period))

            if data.empty:
                return CrawlResult.fail("No K-line data received", source=self.name)

            kline_data = self._parse_kline(data, stock_code)
            return CrawlResult.ok(kline_data, source=self.name)

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

        # A-share: sh600519 -> 600519.SS, sz000001 -> 000001.SZ
        if code.startswith("SH"):
            return f"{code[2:]}.SS"
        elif code.startswith("SZ"):
            return f"{code[2:]}.SZ"

        # HK-share: keep as is (e.g., 0700.HK)
        if ".HK" in code:
            return code

        # US-stock: return as is
        return code

    def _get_interval(self, period: str) -> str:
        """Get yfinance interval parameter.

        Args:
            period: Period type.

        Returns:
            yfinance interval string.
        """
        intervals = {
            "day": "1d",
            "week": "5d",
            "month": "1mo",
        }
        return intervals.get(period, "1d")

    def _parse_kline(self, data, stock_code: str) -> dict:
        """Parse K-line data from yfinance response.

        Args:
            data: yfinance download result.
            stock_code: Stock code.

        Returns:
            Parsed K-line data dictionary.
        """
        klines = []

        # Handle MultiIndex columns (newer yfinance versions)
        if isinstance(data.columns, pd.MultiIndex):
            data = data.droplevel("Ticker", axis=1)

        for idx, row in data.iterrows():
            klines.append({
                "date": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]) if not pd.isna(row["Open"]) else None,
                "high": float(row["High"]) if not pd.isna(row["High"]) else None,
                "low": float(row["Low"]) if not pd.isna(row["Low"]) else None,
                "close": float(row["Close"]) if not pd.isna(row["Close"]) else None,
                "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
            })

        return {
            "stock_code": stock_code,
            "klines": klines,
            "count": len(klines),
            "start_date": klines[0]["date"] if klines else None,
            "end_date": klines[-1]["date"] if klines else None,
        }

    def format_markdown(self, data: dict, show_recent: int = 10) -> str:
        """Format K-line data as Markdown table.

        Args:
            data: K-line data dictionary.
            show_recent: Number of recent days to show.

        Returns:
            Markdown formatted table.
        """
        klines = data.get("klines", [])[-show_recent:]

        md = f"""## K-Line Data (Last {show_recent} Trading Days)

| Date | Open | High | Low | Close | Volume |
|------|------|------|-----|-------|--------|
"""
        for k in klines:
            md += f"| {k['date']} | {self._format_number(k['open'])} | {self._format_number(k['high'])} | {self._format_number(k['low'])} | {self._format_number(k['close'])} | {self._format_number(k['volume'], 0)} |\n"

        md += f"\n*Total {data.get('count', 0)} trading days ({data.get('start_date')} ~ {data.get('end_date')})*"
        return md
