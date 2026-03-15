"""股价数据采集器"""

import aiohttp
from typing import Optional
from datetime import datetime

from .base import BaseCollector, CrawlResult


class PriceCollector(BaseCollector):
    """股价数据采集器 - 支持 A 股、港股、美股"""

    name = "price_collector"
    description = "采集股票实时价格数据"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None

    def validate_params(self, stock_code: str, **kwargs) -> bool:
        return bool(stock_code) and len(stock_code) >= 2

    async def collect(
        self,
        stock_code: str,
        **kwargs,
    ) -> CrawlResult:
        """
        采集股票价格数据

        Args:
            stock_code: 股票代码

        Returns:
            CrawlResult 包含价格数据
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
                return CrawlResult.fail(f"不支持的市场类型：{market}", source=self.name)

            if data:
                return CrawlResult.ok(data, source=self.name)
            return CrawlResult.fail("未获取到数据", source=self.name)

        except Exception as e:
            return CrawlResult.fail(str(e), source=self.name)

    async def _fetch_cn_price(self, stock_code: str) -> Optional[dict]:
        """获取 A 股价格（新浪接口）"""
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
        """获取港股价格（新浪接口）"""
        # 港股代码转换：00700 -> hk00700
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
        """获取美股价格（新浪接口）"""
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
        """解析 A 股行情数据"""
        # 格式：var hq_str_sh600519="贵州茅台，2024-03-15,1688.00,1690.00,1688.00,1700.00,1680.00,..."
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
        """解析港股行情数据"""
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
        """解析美股行情数据"""
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
        """格式化为 Markdown 表格"""
        return f"""## 实时股价

| 项目 | 数值 |
|------|------|
| 股票代码 | {data.get('stock_code', 'N/A')} |
| 股票名称 | {data.get('name', 'N/A')} |
| 当前价格 | {self._format_currency(data.get('current_price'), data.get('currency', '$'))} |
| 涨跌幅 | {self._format_percent(data.get('change_percent'))} |
| 涨跌额 | {self._format_currency(data.get('change'), data.get('currency', '$'))} |
| 开盘价 | {self._format_currency(data.get('open'), data.get('currency', '$'))} |
| 最高价 | {self._format_currency(data.get('high'), data.get('currency', '$'))} |
| 最低价 | {self._format_currency(data.get('low'), data.get('currency', '$'))} |
| 昨收价 | {self._format_currency(data.get('prev_close'), data.get('currency', '$'))} |
| 成交量 | {self._format_number(data.get('volume'), 0)} |
"""
