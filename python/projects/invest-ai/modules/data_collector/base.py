"""数据采集器基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime


@dataclass
class CrawlResult:
    """爬虫结果"""

    success: bool
    data: Any = None
    error: Optional[str] = None
    source: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any, source: str = "", metadata: dict = None) -> "CrawlResult":
        return cls(
            success=True,
            data=data,
            source=source,
            metadata=metadata or {},
        )

    @classmethod
    def fail(cls, error: str, source: str = "") -> "CrawlResult":
        return cls(
            success=False,
            error=error,
            source=source,
        )


class BaseCollector(ABC):
    """数据采集器基类"""

    name: str = "base_collector"
    description: str = "基础数据采集器"

    @abstractmethod
    async def collect(self, **kwargs) -> CrawlResult:
        """采集数据"""
        pass

    @abstractmethod
    def validate_params(self, **kwargs) -> bool:
        """验证参数"""
        pass

    def _format_currency(self, value: float | None, symbol: str = "$") -> str:
        """格式化货币显示"""
        if value is None:
            return "N/A"
        return f"{symbol}{value:,.2f}"

    def _format_percent(self, value: float | None) -> str:
        """格式化百分比"""
        if value is None:
            return "N/A"
        return f"{value:+.2f}%"

    def _format_number(self, value: float | None, decimals: int = 2) -> str:
        """格式化数字"""
        if value is None:
            return "N/A"
        return f"{value:,.{decimals}f}"

    def _detect_market(self, stock_code: str) -> str:
        """
        检测股票市场

        返回：'CN' (A 股), 'HK' (港股), 'US' (美股)
        """
        code = stock_code.lower()

        # A 股：sh 或 sz 开头
        if code.startswith("sh") or code.startswith("sz"):
            return "CN"

        # 港股：HK 结尾或 5 位数字
        if code.endswith("hk") or (code.replace(".", "").isdigit() and len(code) <= 5):
            return "HK"

        # 美股：字母组成
        if code.isalpha():
            return "US"

        return "UNKNOWN"
