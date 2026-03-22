"""Stock price data collector."""

import aiohttp
from datetime import datetime
from typing import Optional

from .base import BaseCollector, CrawlResult


class PriceCollector(BaseCollector):
    """Stock price collector supporting A-share, HK-share, and US-stock.

    This collector uses Sina Finance API to fetch real-time stock prices.
    """

    name = "price_collector"
    description = "Collect real-time stock price data"

    def __init__(self, timeout: int = 10):
        """Initialize price collector.

        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    def validate_params(self, stock_code: str, **kwargs) -> bool:
        """Validate stock code parameter.

        Args:
            stock_code: Stock code to validate.

        Returns:
            True if stock code is valid.
        """
        return bool(stock_code) and len(stock_code) >= 2

    async def collect(self, stock_code: str, **kwargs) -> CrawlResult:
        """Collect stock price data.

        Args:
            stock_code: Stock code (e.g., sh600519, sz000001, AAPL).

        Returns:
            CrawlResult with price data.
        """
        market = self._detect_market(stock_code)

        try:
            if market == "CN":
                data = await self._fetch_cn_price(stock_code)
            elif market == "HK":
                data = await self._fetch_hk_price(stock_code)
            elif market == "US":
                data = await self._fetch_us_price(stock_code)
            else:
                return CrawlResult.fail(f"Unsupported market: {market}", source=self.name)

            if data:
                return CrawlResult.ok(data, source=self.name)
            return CrawlResult.fail("No data received", source=self.name)

        except Exception as e:
            return CrawlResult.fail(str(e), source=self.name)

    async def _fetch_cn_price(self, stock_code: str) -> Optional[dict]:
        """Fetch A-share price from Sina API.

        Args:
            stock_code: A-share stock code.

        Returns:
            Price data dictionary or None.
        """
        url = f"http://hq.sinajs.cn/list={stock_code}"
        headers = {
            "Referer": "http://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    text = await resp.text(encoding="gbk")
                    return self._parse_cn_quote(text, stock_code)
        return None

    async def _fetch_hk_price(self, stock_code: str) -> Optional[dict]:
        """Fetch HK-share price from Sina API.

        Args:
            stock_code: HK-share stock code.

        Returns:
            Price data dictionary or None.
        """
        code = stock_code.replace(".HK", "").replace("hk", "")
        url = f"http://hq.sinajs.cn/list=hk{code}"
        headers = {
            "Referer": "http://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    text = await resp.text(encoding="gbk")
                    return self._parse_hk_quote(text, stock_code)
        return None

    async def _fetch_us_price(self, stock_code: str) -> Optional[dict]:
        """Fetch US-stock price from Sina API.

        Args:
            stock_code: US stock symbol.

        Returns:
            Price data dictionary or None.
        """
        url = f"http://hq.sinajs.cn/list=gb_{stock_code.lower()}"
        headers = {
            "Referer": "http://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=self.timeout) as resp:
                if resp.status == 200:
                    text = await resp.text(encoding="gbk")
                    return self._parse_us_quote(text, stock_code)
        return None

    def _parse_cn_quote(self, text: str, stock_code: str) -> Optional[dict]:
        """Parse A-share quote data.

        Args:
            text: Raw quote response text.
            stock_code: Stock code.

        Returns:
            Parsed price data or None.
        """
        if "=" not in text:
            return None

        parts = text.split("=")[1].strip('"').split(",")
        if len(parts) < 32:
            return None

        try:
            current_price = float(parts[3])
            open_price = float(parts[1])
            high_price = float(parts[4])
            low_price = float(parts[5])
            prev_close = float(parts[2])
            volume = int(parts[8])
            amount = float(parts[9])

            change = current_price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close else 0

            return {
                "stock_code": stock_code,
                "name": parts[0],
                "current_price": current_price,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "prev_close": prev_close,
                "volume": volume,
                "amount": amount,
                "timestamp": datetime.now(),
                "market": "CN",
                "currency": "CNY",
            }
        except (ValueError, IndexError):
            return None

    def _parse_hk_quote(self, text: str, stock_code: str) -> Optional[dict]:
        """Parse HK-share quote data.

        Args:
            text: Raw quote response text.
            stock_code: Stock code.

        Returns:
            Parsed price data or None.
        """
        if "=" not in text:
            return None

        parts = text.split("=")[1].strip('"').split(",")
        if len(parts) < 20:
            return None

        try:
            current_price = float(parts[6])
            prev_close = float(parts[2])
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100 if prev_close else 0

            return {
                "stock_code": stock_code,
                "name": parts[1] if len(parts) > 1 else stock_code,
                "current_price": current_price,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "prev_close": prev_close,
                "timestamp": datetime.now(),
                "market": "HK",
                "currency": "HKD",
            }
        except (ValueError, IndexError):
            return None

    def _parse_us_quote(self, text: str, stock_code: str) -> Optional[dict]:
        """Parse US-stock quote data.

        Args:
            text: Raw quote response text.
            stock_code: Stock symbol.

        Returns:
            Parsed price data or None.
        """
        if "=" not in text:
            return None

        parts = text.split("=")[1].strip('"').split(",")
        if len(parts) < 20:
            return None

        try:
            current_price = float(parts[5])
            change = float(parts[6]) if parts[6] else 0
            change_percent = float(parts[32]) if len(parts) > 32 and parts[32] else 0

            return {
                "stock_code": stock_code,
                "name": stock_code,
                "current_price": current_price,
                "change": round(change, 2),
                "change_percent": round(change_percent, 2),
                "timestamp": datetime.now(),
                "market": "US",
                "currency": "USD",
            }
        except (ValueError, IndexError):
            return None

    def format_markdown(self, data: dict) -> str:
        """Format price data as Markdown table.

        Args:
            data: Price data dictionary.

        Returns:
            Markdown formatted table.
        """
        return f"""## Real-Time Stock Price

| Item | Value |
|------|-------|
| Stock Code | {data.get('stock_code', 'N/A')} |
| Stock Name | {data.get('name', 'N/A')} |
| Current Price | {self._format_currency(data.get('current_price'), data.get('currency', '$'))} |
| Change | {self._format_percent(data.get('change_percent'))} |
| Change Amount | {self._format_currency(data.get('change'), data.get('currency', '$'))} |
| Open | {self._format_currency(data.get('open'), data.get('currency', '$'))} |
| High | {self._format_currency(data.get('high'), data.get('currency', '$'))} |
| Low | {self._format_currency(data.get('low'), data.get('currency', '$'))} |
| Prev Close | {self._format_currency(data.get('prev_close'), data.get('currency', '$'))} |
| Volume | {self._format_number(data.get('volume'), 0)} |
"""
