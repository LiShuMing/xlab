"""财务数据采集器"""

import yfinance as yf
from typing import Optional, Any
from datetime import datetime

from .base import BaseCollector, CrawlResult


class FinancialCollector(BaseCollector):
    """财务数据采集器 - 使用 yfinance 获取"""

    name = "financial_collector"
    description = "采集股票财务数据和指标"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def validate_params(self, stock_code: str, **kwargs) -> bool:
        return bool(stock_code)

    async def collect(
        self,
        stock_code: str,
        report_type: str = "all",
        **kwargs,
    ) -> CrawlResult:
        """
        采集财务数据

        Args:
            stock_code: 股票代码
            report_type: 报表类型 (all/income/balance/cashflow)

        Returns:
            CrawlResult 包含财务数据
        """
        try:
            ticker = self._convert_ticker(stock_code)
            info = yf.Ticker(ticker).info

            if not info:
                return CrawlResult.fail("未获取到财务数据", source=self.name)

            financial_data = self._parse_financials(info, stock_code)
            return CrawlResult.ok(financial_data, source=self.name)

        except Exception as e:
            return CrawlResult.fail(str(e), source=self.name)

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

    def _parse_financials(self, info: dict, stock_code: str) -> dict:
        """解析财务数据"""
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
        """安全获取字典值"""
        value = data.get(key)
        if value is None or value == "N/A":
            return None
        return value

    def format_markdown(self, data: dict) -> str:
        """格式化为 Markdown 表格"""
        md = """## 财务指标

### 估值指标
| 指标 | 数值 |
|------|------|
"""
        md += f"| 总市值 | {self._format_valuation(data.get('market_cap'))} |\n"
        md += f"| 企业价值 | {self._format_valuation(data.get('enterprise_value'))} |\n"
        md += f"| 市盈率 (TTM) | {self._format_number(data.get('trailing_pe'))} |\n"
        md += f"| 市净率 | {self._format_number(data.get('price_to_book'))} |\n"
        md += f"| 市销率 | {self._format_number(data.get('price_to_sales'))} |\n"

        md += """
### 盈利能力
| 指标 | 数值 |
|------|------|
"""
        md += f"| 净利率 | {self._format_percent(data.get('profit_margin'))} |\n"
        md += f"| 营业利润率 | {self._format_percent(data.get('operating_margin'))} |\n"
        md += f"| 净资产收益率 | {self._format_percent(data.get('return_on_equity'))} |\n"
        md += f"| 总资产收益率 | {self._format_percent(data.get('return_on_assets'))} |\n"

        md += """
### 增长能力
| 指标 | 数值 |
|------|------|
"""
        md += f"| 营收增长率 | {self._format_percent(data.get('revenue_growth'))} |\n"
        md += f"| 盈利增长率 | {self._format_percent(data.get('earnings_growth'))} |\n"

        md += """
### 财务健康
| 指标 | 数值 |
|------|------|
"""
        md += f"| 资产负债率 | {self._format_number(data.get('debt_to_equity'))} |\n"
        md += f"| 流动比率 | {self._format_number(data.get('current_ratio'))} |\n"
        md += f"| 速动比率 | {self._format_number(data.get('quick_ratio'))} |\n"

        return md

    def _format_valuation(self, value: Optional[float]) -> str:
        """格式化估值（亿元）"""
        if value is None:
            return "N/A"
        if value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        return f"{value:.2f}"
