"""新闻资讯采集器"""

import aiohttp
from datetime import datetime, timedelta
from typing import Optional, List

from .base import BaseCollector, CrawlResult


class NewsCollector(BaseCollector):
    """新闻资讯采集器 - 获取财经新闻"""

    name = "news_collector"
    description = "采集市场新闻和资讯"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def validate_params(self, stock_code: Optional[str] = None, limit: int = 20, **kwargs) -> bool:
        return limit > 0 and limit <= 100

    async def collect(
        self,
        stock_code: Optional[str] = None,
        limit: int = 20,
        days: int = 7,
        **kwargs,
    ) -> CrawlResult:
        """
        采集新闻数据

        Args:
            stock_code: 股票代码（可选）
            limit: 返回数量
            days: 最近 N 天

        Returns:
            CrawlResult 包含新闻列表
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
        """获取新闻列表"""
        # 如果没有指定股票，获取宏观新闻
        if not stock_code:
            return await self._fetch_macro_news(limit)

        # 使用 yfinance 获取股票新闻
        return await self._fetch_stock_news(stock_code, limit)

    async def _fetch_stock_news(self, stock_code: str, limit: int) -> List[dict]:
        """获取个股新闻（yfinance）"""
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
                    "published_at": datetime.fromtimestamp(item.get("providerPublishTime", 0)).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "summary": item.get("summary", "")[:200] + "..." if item.get("summary") else "",
                })

            return news_list
        except Exception:
            return []

    async def _fetch_macro_news(self, limit: int) -> List[dict]:
        """获取宏观财经新闻（新浪财经）"""
        url = "https://finance.sina.com.cn/roll/index.shtml"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml",
        }

        # 简化版本：返回模拟数据
        # 实际项目中应实现真实的爬虫
        return [
            {
                "title": "央行：保持流动性合理充裕",
                "source": "新浪财经",
                "link": "https://finance.sina.com.cn",
                "published_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "summary": "央行表示将继续实施稳健的货币政策，保持流动性合理充裕...",
            }
        ]

    def _convert_ticker(self, stock_code: str) -> str:
        """转换股票代码为 yfinance 格式"""
        code = stock_code.upper()
        if code.startswith("SH"):
            return f"{code[2:]}.SS"
        elif code.startswith("SZ"):
            return f"{code[2:]}.SZ"
        if ".HK" in code:
            return code
        return code

    def format_markdown(self, data: dict) -> str:
        """格式化为 Markdown"""
        news_list = data.get("news", [])

        if not news_list:
            return "## 市场新闻\n\n暂无相关新闻数据"

        md = f"""## 市场新闻（{data.get('count', 0)}条）

"""
        for i, news in enumerate(news_list[:10], 1):
            md += f"""### {i}. {news.get('title', '无标题')}
- **来源**: {news.get('source', '未知')}
- **时间**: {news.get('published_at', '未知')}
- **链接**: [{news.get('link', '查看')}]({news.get('link', '#')})
- **摘要**: {news.get('summary', '无摘要')}

"""
        return md
