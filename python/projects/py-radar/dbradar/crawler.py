"""Smart web crawler for non-RSS sources with deduplication support.

This module provides intelligent crawling capabilities for sources that don't have
RSS feeds or where RSS feeds are incomplete. It uses URL normalization and content
fingerprinting to avoid duplicates.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

if TYPE_CHECKING:
    from dbradar.fetcher import FetchResult
    from dbradar.extractor import ExtractedItem


@dataclass
class CrawledItem:
    """An item crawled from a web page."""

    url: str
    title: str
    content: str
    published_at: Optional[str]
    author: Optional[str]
    source_url: str  # The page where this item was found
    content_hash: str  # For deduplication


@dataclass
class CrawlRule:
    """Rules for crawling a specific domain."""

    # URL patterns to include (regex)
    include_patterns: List[str] = field(default_factory=list)
    # URL patterns to exclude (regex)
    exclude_patterns: List[str] = field(default_factory=list)
    # CSS selectors for article links
    link_selectors: List[str] = field(default_factory=lambda: [
        "article a[href]",
        ".post a[href]",
        ".entry a[href]",
        "h2 a[href]",
        "h3 a[href]",
        ".blog-post a[href]",
    ])
    # CSS selectors for article content
    content_selectors: List[str] = field(default_factory=lambda: [
        "article",
        ".post-content",
        ".entry-content",
        "[class*='content']",
        "main",
    ])
    # CSS selectors for date extraction
    date_selectors: List[str] = field(default_factory=lambda: [
        "time[datetime]",
        "[class*='date']",
        "[class*='published']",
        "meta[property='article:published_time']",
    ])
    # Maximum pages to crawl per source
    max_pages: int = 3
    # Whether to follow pagination
    follow_pagination: bool = True


class URLNormalizer:
    """Normalize URLs for deduplication."""

    # Common tracking parameters to remove
    TRACKING_PARAMS = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'fbclid', 'gclid', 'ref', 'referrer', 'source',
    }

    @classmethod
    def normalize(cls, url: str) -> str:
        """Normalize a URL for comparison.

        - Lowercase scheme and domain
        - Remove www. prefix
        - Remove tracking parameters
        - Remove fragment
        - Ensure consistent trailing slash handling
        """
        parsed = urlparse(url)

        # Normalize domain
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        if netloc.startswith('www.'):
            netloc = netloc[4:]

        # Normalize path
        path = parsed.path
        if not path:
            path = '/'

        # Remove tracking parameters
        if parsed.query:
            params = []
            for param in parsed.query.split('&'):
                if '=' in param:
                    key = param.split('=')[0].lower()
                    if key not in cls.TRACKING_PARAMS:
                        params.append(param)
            query = '&'.join(params) if params else ''
        else:
            query = ''

        # Reconstruct URL without fragment
        normalized = f"{scheme}://{netloc}{path}"
        if query:
            normalized += f"?{query}"

        return normalized

    @classmethod
    def get_canonical_url(cls, url: str, html_content: str) -> str:
        """Extract canonical URL from HTML if available.

        Always returns an absolute URL. If the canonical link is relative,
        it will be resolved against the original URL.
        """
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            canonical = soup.find('link', rel='canonical')
            if canonical and canonical.get('href'):
                canonical_href = canonical['href']
                # If canonical is relative, resolve it against the original URL
                if canonical_href.startswith('/'):
                    return urljoin(url, canonical_href)
                return canonical_href
        except Exception:
            pass
        return url


class ContentFingerprinter:
    """Generate fingerprints for content deduplication."""

    @staticmethod
    def fingerprint(text: str) -> str:
        """Generate a content fingerprint using simhash-like approach.

        Uses first 3 sentences normalized for quick comparison.
        """
        # Normalize text
        normalized = text.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)

        # Take first ~200 chars which usually covers title + first sentence
        sample = normalized[:200]

        # Generate hash
        return hashlib.md5(sample.encode('utf-8')).hexdigest()[:16]

    @staticmethod
    def similarity(fp1: str, fp2: str) -> float:
        """Calculate similarity between two fingerprints.

        For MD5-based fingerprints, this is binary (same or different).
        Future: Could use simhash for near-duplicate detection.
        """
        return 1.0 if fp1 == fp2 else 0.0


class SmartCrawler:
    """Intelligent crawler for non-RSS sources."""

    USER_AGENT = (
        "Mozilla/5.0 (compatible; DBRadar/0.1; +https://github.com/dbradar)"
    )

    # Domain-specific crawl rules
    DOMAIN_RULES: dict[str, CrawlRule] = {
        "clickhouse.com": CrawlRule(
            include_patterns=[r"/blog/"],
            exclude_patterns=[r"/blog/\d+$", r"/blog/tag/", r"/blog/author/"],
            link_selectors=[
                "article a[href^='/blog/']",
                ".blog-card a[href]",
                "h2 a[href^='/blog/']",
            ],
            max_pages=2,
        ),
        "github.com": CrawlRule(
            include_patterns=[r"/releases/tag/"],
            exclude_patterns=[r"/compare/", r"/tree/", r"/blob/"],
            max_pages=1,
        ),
    }

    def __init__(
        self,
        timeout: float = 30.0,
        respect_robots: bool = True,
        delay: float = 1.0,
    ):
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.delay = delay
        self._seen_urls: Set[str] = set()
        self._seen_fingerprints: Set[str] = set()
        self.url_normalizer = URLNormalizer()
        self.fingerprinter = ContentFingerprinter()

    def _get_rule(self, url: str) -> CrawlRule:
        """Get crawl rule for a URL."""
        domain = urlparse(url).netloc.lower()
        # Remove www. prefix for matching
        if domain.startswith('www.'):
            domain = domain[4:]

        # Try exact domain match
        if domain in self.DOMAIN_RULES:
            return self.DOMAIN_RULES[domain]

        # Try partial match
        for rule_domain, rule in self.DOMAIN_RULES.items():
            if rule_domain in domain:
                return rule

        # Return default rule
        return CrawlRule()

    def _should_crawl(self, url: str, rule: CrawlRule) -> bool:
        """Check if URL should be crawled based on rules."""
        # Check normalized URL not seen
        normalized = self.url_normalizer.normalize(url)
        if normalized in self._seen_urls:
            return False

        # Check include patterns
        if rule.include_patterns:
            if not any(re.search(p, url) for p in rule.include_patterns):
                return False

        # Check exclude patterns
        if any(re.search(p, url) for p in rule.exclude_patterns):
            return False

        return True

    def _extract_article_links(
        self, soup: BeautifulSoup, base_url: str, rule: CrawlRule
    ) -> List[str]:
        """Extract article links from a page."""
        links = []
        seen = set()

        for selector in rule.link_selectors:
            for tag in soup.select(selector):
                href = tag.get('href')
                if not href:
                    continue

                # Resolve relative URLs
                full_url = urljoin(base_url, href)

                # Skip non-HTTP URLs
                if not full_url.startswith(('http://', 'https://')):
                    continue

                # Normalize and dedupe
                normalized = self.url_normalizer.normalize(full_url)
                if normalized in seen:
                    continue
                seen.add(normalized)

                # Check rules
                if self._should_crawl(full_url, rule):
                    links.append(full_url)

        return links

    def _extract_content(
        self, soup: BeautifulSoup, rule: CrawlRule
    ) -> tuple[str, str]:
        """Extract title and content from article page."""
        # Try to find title
        title = ""
        for selector in ["h1", "article h1", ".post-title", "[class*='title']"]:
            tag = soup.select_one(selector)
            if tag:
                title = tag.get_text(strip=True)
                break

        # Try to find content
        content = ""
        for selector in rule.content_selectors:
            tag = soup.select_one(selector)
            if tag:
                # Remove script/style tags
                for script in tag.find_all(["script", "style", "nav", "header", "footer"]):
                    script.decompose()
                content = tag.get_text(separator=' ', strip=True)
                if len(content) > 200:  # Minimum content length
                    break

        return title, content

    def _extract_date(self, soup: BeautifulSoup, rule: CrawlRule) -> Optional[str]:
        """Extract publication date from page."""
        for selector in rule.date_selectors:
            tag = soup.select_one(selector)
            if not tag:
                continue

            # Try datetime attribute
            if tag.get('datetime'):
                return tag['datetime']

            # Try content attribute (meta tags)
            if tag.get('content'):
                return tag['content']

            # Try text content
            text = tag.get_text(strip=True)
            if text:
                # Try to parse various date formats
                for fmt in ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d %B %Y"]:
                    try:
                        dt = datetime.strptime(text, fmt)
                        return dt.replace(tzinfo=timezone.utc).isoformat()
                    except ValueError:
                        continue

        return None

    def crawl_article(self, client: httpx.Client, url: str) -> Optional[CrawledItem]:
        """Crawl a single article page."""
        try:
            response = client.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # Get canonical URL
            canonical_url = self.url_normalizer.get_canonical_url(url, response.text)
            normalized_url = self.url_normalizer.normalize(canonical_url)

            # Skip if already seen
            if normalized_url in self._seen_urls:
                return None

            # Extract content
            rule = self._get_rule(url)
            title, content = self._extract_content(soup, rule)

            if not title or len(content) < 100:
                return None

            # Generate fingerprint
            fingerprint = self.fingerprinter.fingerprint(f"{title} {content[:500]}")

            # Skip if content fingerprint seen
            if fingerprint in self._seen_fingerprints:
                return None

            # Extract date
            published_at = self._extract_date(soup, rule)

            # Mark as seen
            self._seen_urls.add(normalized_url)
            self._seen_fingerprints.add(fingerprint)

            return CrawledItem(
                url=canonical_url,
                title=title,
                content=content,
                published_at=published_at,
                author=None,  # Could extract from meta tags
                source_url=url,
                content_hash=fingerprint,
            )

        except Exception as e:
            # Log error but don't fail entire crawl
            print(f"Error crawling {url}: {e}")
            return None

    def crawl_source(self, start_url: str) -> List[CrawledItem]:
        """Crawl a source starting from a URL.

        Args:
            start_url: The starting URL (usually a blog index page).

        Returns:
            List of crawled items.
        """
        items = []
        rule = self._get_rule(start_url)

        with httpx.Client(timeout=self.timeout) as client:
            # First, fetch the index page
            try:
                response = client.get(
                    start_url,
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=self.timeout,
                )
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'lxml')

                # Extract article links
                article_links = self._extract_article_links(soup, start_url, rule)
                print(f"Found {len(article_links)} article links on {start_url}")

                # Crawl each article
                for link in article_links[:20]:  # Limit to first 20 articles
                    item = self.crawl_article(client, link)
                    if item:
                        items.append(item)

                # TODO: Follow pagination if enabled and max_pages > 1

            except Exception as e:
                print(f"Error crawling source {start_url}: {e}")

        return items

    def crawl_feed_result(self, result: FetchResult) -> List[CrawledItem]:
        """Crawl items from a feed fetch result.

        This is the main entry point for integrating with the existing fetcher.
        It handles both RSS feeds (passthrough) and HTML pages (crawl).
        """
        # Check if content is RSS/Atom
        content_start = result.content[:500].lower()
        is_rss = any(tag in content_start for tag in ['<rss', '<feed', '<channel', '<item'])

        if is_rss:
            # RSS content - no crawling needed
            return []

        # HTML content - crawl for article links
        return self.crawl_source(result.url)


def crawl_non_rss_sources(results: List[FetchResult]) -> List[CrawledItem]:
    """Convenience function to crawl non-RSS sources.

    Args:
        results: List of fetch results.

    Returns:
        List of crawled items from non-RSS sources.
    """
    crawler = SmartCrawler()
    all_items = []

    for result in results:
        if result.content_type == "error" or not result.content:
            continue

        items = crawler.crawl_feed_result(result)
        all_items.extend(items)

    return all_items
