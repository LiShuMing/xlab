"""Radar crawler compatibility wrapper backed by shared web crawler."""

from backend._shared.web_crawler import (
    ContentFingerprinter,
    CrawledItem,
    CrawlRule,
    SmartCrawler,
    URLNormalizer,
    crawl_non_rss_sources,
)

__all__ = [
    "ContentFingerprinter",
    "CrawledItem",
    "CrawlRule",
    "SmartCrawler",
    "URLNormalizer",
    "crawl_non_rss_sources",
]
