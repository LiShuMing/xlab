"""Data collector module."""

from backend.invest.modules.data_collector.financial_collector import FinancialCollector
from backend.invest.modules.data_collector.kline_collector import KLineCollector
from backend.invest.modules.data_collector.news_collector import NewsCollector
from backend.invest.modules.data_collector.price_collector import PriceCollector

__all__ = ["PriceCollector", "FinancialCollector", "KLineCollector", "NewsCollector"]
