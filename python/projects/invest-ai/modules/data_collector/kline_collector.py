"""K 线数据采集器"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional

from .base import BaseCollector, CrawlResult

# 需要 pandas 支持
try:
    import pandas as pd
except ImportError:
    pd = None


class KLineCollector(BaseCollector):
    """K 线数据采集器 - 使用 yfinance 获取"""

    name = "kline_collector"
    description = "采集股票 K 线数据（OHLCV）"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def validate_params(self, stock_code: str, days: int = 90, **kwargs) -> bool:
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
        """
        采集 K 线数据

        Args:
            stock_code: 股票代码
            days: 获取天数
            period: 周期 (day/week/month)

        Returns:
            CrawlResult 包含 K 线数据
        """
        try:
            ticker = self._convert_ticker(stock_code)
            data = yf.download(ticker, period=f"{days}d", interval=self._get_interval(period))

            if data.empty:
                return CrawlResult.fail("未获取到 K 线数据", source=self.name)

            kline_data = self._parse_kline(data, stock_code)
            return CrawlResult.ok(kline_data, source=self.name)

        except Exception as e:
            return CrawlResult.fail(str(e), source=self.name)

    def _convert_ticker(self, stock_code: str) -> str:
        """转换股票代码为 yfinance 格式"""
        code = stock_code.upper()

        # A 股：sh600519 -> 600519.SS, sz000001 -> 000001.SZ
        if code.startswith("SH"):
            return f"{code[2:]}.SS"
        elif code.startswith("SZ"):
            return f"{code[2:]}.SZ"

        # 港股：0700.HK 保持不变
        if ".HK" in code:
            return code

        # 美股：直接返回
        return code

    def _get_interval(self, period: str) -> str:
        """获取 yfinance 时间间隔参数"""
        intervals = {
            "day": "1d",
            "week": "5d",
            "month": "1mo",
        }
        return intervals.get(period, "1d")

    def _parse_kline(self, data, stock_code: str) -> dict:
        """解析 K 线数据"""
        klines = []

        # 处理 MultiIndex 列（新版本的 yfinance）
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
        """格式化为 Markdown 表格"""
        klines = data.get("klines", [])[-show_recent:]

        md = f"""## K 线数据（最近{show_recent}个交易日）

| 日期 | 开盘 | 最高 | 最低 | 收盘 | 成交量 |
|------|------|------|------|------|--------|
"""
        for k in klines:
            md += f"| {k['date']} | {self._format_number(k['open'])} | {self._format_number(k['high'])} | {self._format_number(k['low'])} | {self._format_number(k['close'])} | {self._format_number(k['volume'], 0)} |\n"

        md += f"\n*共 {data.get('count', 0)} 个交易日数据 ({data.get('start_date')} ~ {data.get('end_date')})*"
        return md
