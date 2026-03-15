"""Agent 工具实现"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Optional

from .base import BaseAgentTool, ToolInfo, ToolParameter, ToolResult
from modules.data_collector import (
    PriceCollector,
    KLineCollector,
    FinancialCollector,
    NewsCollector,
)


class QueryStockPriceTool(BaseAgentTool):
    """股价查询工具"""

    name = "query_stock_price"
    description = "查询股票实时价格"

    def __init__(self):
        self._collector = PriceCollector()

    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name=self.name,
            description="获取股票的实时股价、涨跌幅、成交量等数据",
            parameters=[
                ToolParameter(
                    name="stock_code",
                    type="string",
                    description="股票代码，如 sh600519(茅台),sz000001(平安),AAPL(苹果)",
                    required=True,
                ),
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        stock_code = arguments.get("stock_code", "")
        if not stock_code:
            return ToolResult.fail("股票代码不能为空", self.name).result

        result = await self._collector.collect(stock_code=stock_code)
        if result.success:
            return PriceCollector().format_markdown(result.data)
        return ToolResult.fail(result.error or "获取失败", self.name).result


class QueryKLineDataTool(BaseAgentTool):
    """K 线数据查询工具"""

    name = "query_kline_data"
    description = "查询股票 K 线数据"

    def __init__(self):
        self._collector = KLineCollector()

    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name=self.name,
            description="获取股票的历史 K 线数据，包括开盘价、最高价、最低价、收盘价、成交量",
            parameters=[
                ToolParameter(
                    name="stock_code",
                    type="string",
                    description="股票代码",
                    required=True,
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="获取 K 线的天数，默认 90 天，最大 365 天",
                    required=False,
                    default=90,
                ),
                ToolParameter(
                    name="period",
                    type="string",
                    description="K 线周期：day(日线), week(周线), month(月线)",
                    required=False,
                    default="day",
                    enum=["day", "week", "month"],
                ),
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        stock_code = arguments.get("stock_code", "")
        days = arguments.get("days", 90)
        period = arguments.get("period", "day")

        result = await self._collector.collect(stock_code=stock_code, days=days, period=period)
        if result.success:
            return KLineCollector().format_markdown(result.data)
        return ToolResult.fail(result.error or "获取失败", self.name).result


class QueryFinancialMetricsTool(BaseAgentTool):
    """财务指标查询工具"""

    name = "query_financial_metrics"
    description = "查询股票财务指标"

    def __init__(self):
        self._collector = FinancialCollector()

    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name=self.name,
            description="查询股票的财务指标，包括估值、盈利能力、增长能力、财务健康等",
            parameters=[
                ToolParameter(
                    name="stock_code",
                    type="string",
                    description="股票代码",
                    required=True,
                ),
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        stock_code = arguments.get("stock_code", "")
        if not stock_code:
            return ToolResult.fail("股票代码不能为空", self.name).result

        result = await self._collector.collect(stock_code=stock_code)
        if result.success:
            return FinancialCollector().format_markdown(result.data)
        return ToolResult.fail(result.error or "获取失败", self.name).result


class QueryMarketNewsTool(BaseAgentTool):
    """市场新闻查询工具"""

    name = "query_market_news"
    description = "查询市场新闻"

    def __init__(self):
        self._collector = NewsCollector()

    def get_info(self) -> ToolInfo:
        return ToolInfo(
            name=self.name,
            description="获取市场新闻、财经资讯，支持按股票或宏观新闻筛选",
            parameters=[
                ToolParameter(
                    name="stock_code",
                    type="string",
                    description="股票代码（可选），不传则返回宏观新闻",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="返回新闻条数，默认 20 条",
                    required=False,
                    default=20,
                ),
                ToolParameter(
                    name="days",
                    type="integer",
                    description="最近 N 天的新闻，默认 7 天",
                    required=False,
                    default=7,
                ),
            ],
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        stock_code = arguments.get("stock_code")
        limit = arguments.get("limit", 20)
        days = arguments.get("days", 7)

        result = await self._collector.collect(stock_code=stock_code, limit=limit, days=days)
        if result.success:
            return NewsCollector().format_markdown(result.data)
        return ToolResult.fail(result.error or "获取失败", self.name).result
