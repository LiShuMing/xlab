"""Integration layer between SmartCrawler and existing extraction pipeline.

This module bridges the gap between the new SmartCrawler and the existing
extractor/normalizer pipeline, ensuring crawled items are properly deduplicated
with RSS-extracted items.
"""

from __future__ import annotations

from typing import List, Optional

from dbradar.crawler import CrawledItem, SmartCrawler, crawl_non_rss_sources
from dbradar.extractor import ExtractedItem
from dbradar.fetcher import FetchResult


class CrawlerAdapter:
    """Adapter to convert CrawledItem to ExtractedItem."""

    @staticmethod
    def to_extracted_item(crawled: CrawledItem, product: str) -> ExtractedItem:
        """Convert a CrawledItem to ExtractedItem.

        Args:
            crawled: Item from SmartCrawler.
            product: Product name for categorization.

        Returns:
            ExtractedItem compatible with existing pipeline.
        """
        # Determine content type based on title and content
        content_type = CrawlerAdapter._classify_content(crawled.title, crawled.content)

        # Calculate confidence based on content quality
        confidence = CrawlerAdapter._calculate_confidence(crawled.title, crawled.content)

        return ExtractedItem(
            url=crawled.url,
            product=product,
            title=crawled.title,
            content=crawled.content,
            html_content="",  # Not storing full HTML to save memory
            published_at=crawled.published_at,
            author=crawled.author,
            content_type=content_type,
            confidence=confidence,
        )

    @staticmethod
    def _classify_content(title: str, content: str) -> str:
        """Classify content type based on title and content."""
        text = f"{title} {content}".lower()

        release_keywords = [
            "release", "released", "announcing", "announcement",
            "version", "changelog", "what's new", "v1.", "v2.", "v0.",
        ]
        benchmark_keywords = [
            "benchmark", "performance", "speed test", "throughput",
            "latency", "tpc-", "ycsb", "sysbench",
        ]
        tutorial_keywords = [
            "how to", "tutorial", "guide", "getting started",
            "introduction", "walkthrough", "example",
        ]

        if any(kw in text for kw in release_keywords):
            return "release"
        elif any(kw in text for kw in benchmark_keywords):
            return "benchmark"
        elif any(kw in text for kw in tutorial_keywords):
            return "tutorial"
        else:
            return "blog"

    @staticmethod
    def _calculate_confidence(title: str, content: str) -> float:
        """Calculate confidence score for crawled content."""
        score = 0.5  # Base score for crawled content

        # Boost for good title length
        title_len = len(title)
        if 20 <= title_len <= 100:
            score += 0.1

        # Boost for substantial content
        content_len = len(content)
        if content_len > 1000:
            score += 0.2
        elif content_len > 500:
            score += 0.1

        # Boost for database-related keywords
        db_keywords = [
            "database", "db", "sql", "query", "storage", "index",
            "transaction", "performance", "optimization", "engine",
            "postgresql", "mysql", "clickhouse", "mongodb", "redis",
            "duckdb", "sqlite", "parquet", "lakehouse", "warehouse",
        ]
        text = f"{title} {content[:500]}".lower()
        keyword_matches = sum(1 for kw in db_keywords if kw in text)
        score += min(keyword_matches * 0.05, 0.2)

        return min(score, 1.0)


def extract_with_crawler(
    fetch_results: List[FetchResult],
    enable_crawler: bool = True,
) -> List[ExtractedItem]:
    """Extract items from fetch results with crawler enhancement.

    This is the main entry point that combines RSS extraction with
    intelligent crawling for non-RSS sources.

    Args:
        fetch_results: Results from Fetcher.fetch_feeds().
        enable_crawler: Whether to enable crawler for non-RSS sources.

    Returns:
        List of ExtractedItem from both RSS and crawled sources.
    """
    from dbradar.extractor import Extractor

    extractor = Extractor()
    adapter = CrawlerAdapter()
    all_items: List[ExtractedItem] = []

    # Track URLs to avoid duplicates between RSS and crawled content
    seen_urls = set()

    # Step 1: Extract from RSS feeds
    for result in fetch_results:
        if result.content_type == "error" or not result.content:
            continue

        # Check if RSS content
        content_start = result.content[:500].lower()
        is_rss = any(tag in content_start for tag in ['<rss', '<feed', '<channel', '<item'])

        if is_rss:
            items = extractor.extract_rss_items(result)
            for item in items:
                normalized_url = SmartCrawler.url_normalizer.normalize(item.url)
                if normalized_url not in seen_urls:
                    seen_urls.add(normalized_url)
                    all_items.append(item)

    # Step 2: Crawl non-RSS sources if enabled
    if enable_crawler:
        crawler = SmartCrawler()

        for result in fetch_results:
            if result.content_type == "error" or not result.content:
                continue

            # Skip RSS feeds
            content_start = result.content[:500].lower()
            is_rss = any(tag in content_start for tag in ['<rss', '<feed', '<channel', '<item'])

            if is_rss:
                continue

            # Crawl this source
            print(f"Crawling non-RSS source: {result.product} ({result.url})")
            crawled_items = crawler.crawl_feed_result(result)

            for crawled in crawled_items:
                # Check for duplicates with RSS-extracted items
                normalized_url = SmartCrawler.url_normalizer.normalize(crawled.url)
                if normalized_url in seen_urls:
                    print(f"  Skipping duplicate: {crawled.url}")
                    continue

                seen_urls.add(normalized_url)

                # Convert to ExtractedItem
                extracted = adapter.to_extracted_item(crawled, result.product)
                all_items.append(extracted)
                print(f"  Added: {extracted.title[:60]}...")

    return all_items


def dedupe_extracted_items(items: List[ExtractedItem]) -> List[ExtractedItem]:
    """Deduplicate extracted items using URL and content fingerprinting.

    Args:
        items: List of extracted items (from RSS or crawling).

    Returns:
        Deduplicated list of items.
    """
    from dbradar.crawler import URLNormalizer, ContentFingerprinter

    seen_urls: set[str] = set()
    seen_fingerprints: set[str] = set()
    unique_items: List[ExtractedItem] = []

    for item in items:
        # Normalize URL
        normalized_url = URLNormalizer.normalize(item.url)

        # Generate content fingerprint
        fingerprint = ContentFingerprinter.fingerprint(
            f"{item.title} {item.content[:300]}"
        )

        # Check for duplicates
        if normalized_url in seen_urls:
            continue

        if fingerprint in seen_fingerprints:
            print(f"Duplicate content (fingerprint): {item.title[:50]}...")
            continue

        seen_urls.add(normalized_url)
        seen_fingerprints.add(fingerprint)
        unique_items.append(item)

    print(f"Deduplication: {len(items)} -> {len(unique_items)} items")
    return unique_items
