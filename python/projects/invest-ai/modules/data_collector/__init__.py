"""数据收集模块 - 支持多市场股票数据"""

__version__ = "0.1.0"

from .base import BaseCollector, CrawlResult
from .price_collector import PriceCollector
from .kline_collector import KLineCollector
from .financial_collector import FinancialCollector
from .news_collector import NewsCollector

__all__ = [
    "BaseCollector",
    "CrawlResult",
    "PriceCollector",
    "KLineCollector",
    "FinancialCollector",
    "NewsCollector",
]
