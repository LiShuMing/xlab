"""News and market information collector."""

import aiohttp
from datetime import datetime, timedelta
from typing import Optional, List

from .base import BaseCollector, CrawlResult


class NewsCollector(BaseCollector):
    """News and market information collector.

    Fetches stock-specific news and macroeconomic news.
    """

    name = "news_collector"
    description = "Collect market news and financial information"

    def __init__(self, timeout: int = 15):
        """Initialize news collector.

        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout

    def validate_params(self, stock_code: Optional[str] = None, limit: int = 20, **kwargs) -> bool:
        """Validate parameters.

        Args:
            stock_code: Optional stock code.
            limit: Number of news items to fetch.

        Returns:
            True if parameters are valid.
        """
        return limit > 0 and limit <= 100

    async def collect(
        self,
        stock_code: Optional[str] = None,
        limit: int = 20,
        days: int = 7,
        **kwargs,
    ) -> CrawlResult:
        """Collect news data.

        Args:
            stock_code: Stock code (optional, fetches macro news if not provided).
            limit: Number of news items.
            days: Number of days to look back.

        Returns:
            CrawlResult with news data.
        """
        try:
            news_list = await self._fetch_news(stock_code, limit, days)
            return CrawlResult.ok(
                {"stock_code": stock_code, "news": news_list, "count": len(news_list)},
                source=self.name,
            )
        except Exception as e:
            return CrawlResult.fail(str(e), source=self.name)

    async def _fetch_news(
        self,
        stock_code: Optional[str],
        limit: int,
        days: int,
    ) -> List[dict]:
        """Fetch news list.

        Args:
            stock_code: Stock code.
            limit: Number of items.
            days: Days to look back.

        Returns:
            List of news items.
        """
        if not stock_code:
            return await self._fetch_macro_news(limit)
        return await self._fetch_stock_news(stock_code, limit)

    async def _fetch_stock_news(self, stock_code: str, limit: int) -> List[dict]:
        """Fetch stock-specific news from yfinance.

        Args:
            stock_code: Stock code.
            limit: Number of items.

        Returns:
            List of news items.
        """
        try:
            import yfinance as yf

            ticker = self._convert_ticker(stock_code)
            ticker_obj = yf.Ticker(ticker)
            news_data = ticker_obj.news

            if not news_data:
                return []

            news_list = []
            for item in news_data[:limit]:
                news_list.append({
                    "title": item.get("title", ""),
                    "source": item.get("publisher", ""),
                    "link": item.get("link", ""),
                    "published_at": datetime.fromtimestamp(
                        item.get("providerPublishTime", 0)
                    ).strftime("%Y-%m-%d %H:%M"),
                    "summary": (
                        item.get("summary", "")[:200] + "..." if item.get("summary") else ""
                    ),
                })

            return news_list
        except Exception:
            return []

    async def _fetch_macro_news(self, limit: int) -> List[dict]:
        """Fetch macroeconomic news.

        Note: Macro news requires external API integration (e.g., NewsAPI, Alpha Vantage).
        Currently returns empty list - stock-specific news is available via yfinance.

        Args:
            limit: Number of items.

        Returns:
            Empty list (macro news API not configured).
        """
        # TODO: Integrate with macro news API (NewsAPI, Alpha Vantage, etc.)
        # For now, return empty to avoid presenting fake data as real
        return []

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

    def format_markdown(self, data: dict) -> str:
        """Format news data as Markdown.

        Args:
            data: News data dictionary.

        Returns:
            Markdown formatted news list.
        """
        news_list = data.get("news", [])

        if not news_list:
            return "## Market News\n\nNo news available"

        md = f"""## Market News ({data.get('count', 0)} items)

"""
        for i, news in enumerate(news_list[:10], 1):
            md += f"""### {i}. {news.get('title', 'No Title')}
- **Source**: {news.get('source', 'Unknown')}
- **Time**: {news.get('published_at', 'Unknown')}
- **Link**: [{news.get('link', 'View')}]({news.get('link', '#')})
- **Summary**: {news.get('summary', 'No summary')}

"""
        return md
