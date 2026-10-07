"""Shared smart crawler for non-RSS web sources."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from backend._shared.http import HTTPClientConfig, SharedSyncHTTPClient
from backend._shared.urls import TRACKING_PARAMS, normalize_url
from backend._shared.web_feed import is_feed_content
from backend.settings import get_settings as get_runtime_settings


class FetchLike(Protocol):
    url: str
    content: str
    content_type: str


@dataclass
class CrawledItem:
    """An item crawled from a web page."""

    url: str
    title: str
    content: str
    published_at: str | None
    author: str | None
    source_url: str
    content_hash: str


@dataclass
class CrawlRule:
    """Rules for crawling a specific domain."""

    include_patterns: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    link_selectors: list[str] = field(
        default_factory=lambda: [
            "article a[href]",
            ".post a[href]",
            ".entry a[href]",
            "h2 a[href]",
            "h3 a[href]",
            ".blog-post a[href]",
        ]
    )
    content_selectors: list[str] = field(
        default_factory=lambda: [
            "article",
            ".post-content",
            ".entry-content",
            "[class*='content']",
            "main",
        ]
    )
    date_selectors: list[str] = field(
        default_factory=lambda: [
            "time[datetime]",
            "[class*='date']",
            "[class*='published']",
            "meta[property='article:published_time']",
        ]
    )
    max_pages: int = 3
    follow_pagination: bool = True


class URLNormalizer:
    """Normalize URLs for deduplication."""

    TRACKING_PARAMS = TRACKING_PARAMS

    @classmethod
    def normalize(cls, url: str) -> str:
        """Normalize a URL for comparison."""
        return normalize_url(url, cls.TRACKING_PARAMS)

    @classmethod
    def get_canonical_url(cls, url: str, html_content: str) -> str:
        """Extract canonical URL from HTML if available."""
        try:
            soup = BeautifulSoup(html_content, "lxml")
            canonical = soup.find("link", rel="canonical")
            if canonical and canonical.get("href"):
                canonical_href = canonical["href"]
                if canonical_href.startswith("/"):
                    return urljoin(url, canonical_href)
                return canonical_href
        except Exception:
            pass
        return url


class ContentFingerprinter:
    """Generate fingerprints for content deduplication."""

    @staticmethod
    def fingerprint(text: str) -> str:
        """Generate a compact normalized content fingerprint."""
        normalized = text.lower().strip()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = re.sub(r"[^\w\s]", "", normalized)
        sample = normalized[:200]
        return hashlib.md5(sample.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def similarity(fp1: str, fp2: str) -> float:
        """Calculate similarity between two fingerprints."""
        return 1.0 if fp1 == fp2 else 0.0


class SmartCrawler:
    """Intelligent crawler for non-RSS sources."""

    USER_AGENT = "Mozilla/5.0 (compatible; Liminalis/1.0; +https://github.com/xlab/liminalis)"

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
        transport: httpx.BaseTransport | None = None,
    ):
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.delay = delay
        self.transport = transport
        self._seen_urls: set[str] = set()
        self._seen_fingerprints: set[str] = set()
        self.url_normalizer = URLNormalizer()
        self.fingerprinter = ContentFingerprinter()

    def _http_client(self) -> SharedSyncHTTPClient:
        config = HTTPClientConfig.from_settings(
            get_runtime_settings(),
            read_timeout=self.timeout,
            follow_redirects=True,
        )
        return SharedSyncHTTPClient(config, transport=self.transport)

    def _get_rule(self, url: str) -> CrawlRule:
        """Get crawl rule for a URL."""
        domain = urlparse(url).netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        if domain in self.DOMAIN_RULES:
            return self.DOMAIN_RULES[domain]

        for rule_domain, rule in self.DOMAIN_RULES.items():
            if rule_domain in domain:
                return rule

        return CrawlRule()

    def _should_crawl(self, url: str, rule: CrawlRule) -> bool:
        """Check if URL should be crawled based on rules."""
        normalized = self.url_normalizer.normalize(url)
        if normalized in self._seen_urls:
            return False

        if rule.include_patterns and not any(re.search(pattern, url) for pattern in rule.include_patterns):
            return False

        return not any(re.search(pattern, url) for pattern in rule.exclude_patterns)

    def _extract_article_links(self, soup: BeautifulSoup, base_url: str, rule: CrawlRule) -> list[str]:
        """Extract article links from a page."""
        links = []
        seen = set()

        for selector in rule.link_selectors:
            for tag in soup.select(selector):
                href = tag.get("href")
                if not href:
                    continue

                full_url = urljoin(base_url, href)
                if not full_url.startswith(("http://", "https://")):
                    continue

                normalized = self.url_normalizer.normalize(full_url)
                if normalized in seen:
                    continue
                seen.add(normalized)

                if self._should_crawl(full_url, rule):
                    links.append(full_url)

        return links

    def _extract_content(self, soup: BeautifulSoup, rule: CrawlRule) -> tuple[str, str]:
        """Extract title and content from article page."""
        title = ""
        for selector in ["h1", "article h1", ".post-title", "[class*='title']"]:
            tag = soup.select_one(selector)
            if tag:
                title = tag.get_text(strip=True)
                break

        content = ""
        for selector in rule.content_selectors:
            tag = soup.select_one(selector)
            if tag:
                for script in tag.find_all(["script", "style", "nav", "header", "footer"]):
                    script.decompose()
                content = tag.get_text(separator=" ", strip=True)
                if len(content) > 200:
                    break

        return title, content

    def _extract_date(self, soup: BeautifulSoup, rule: CrawlRule) -> str | None:
        """Extract publication date from page."""
        for selector in rule.date_selectors:
            tag = soup.select_one(selector)
            if not tag:
                continue

            if tag.get("datetime"):
                return tag["datetime"]

            if tag.get("content"):
                return tag["content"]

            text = tag.get_text(strip=True)
            if text:
                for fmt in ["%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%d %B %Y"]:
                    try:
                        dt = datetime.strptime(text, fmt)
                        return dt.replace(tzinfo=UTC).isoformat()
                    except ValueError:
                        continue

        return None

    def crawl_article(self, client: httpx.Client | SharedSyncHTTPClient, url: str) -> CrawledItem | None:
        """Crawl a single article page."""
        try:
            response = client.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "lxml")

            canonical_url = self.url_normalizer.get_canonical_url(url, response.text)
            normalized_url = self.url_normalizer.normalize(canonical_url)
            if normalized_url in self._seen_urls:
                return None

            rule = self._get_rule(url)
            title, content = self._extract_content(soup, rule)
            if not title or len(content) < 100:
                return None

            fingerprint = self.fingerprinter.fingerprint(f"{title} {content[:500]}")
            if fingerprint in self._seen_fingerprints:
                return None

            published_at = self._extract_date(soup, rule)

            self._seen_urls.add(normalized_url)
            self._seen_fingerprints.add(fingerprint)

            return CrawledItem(
                url=canonical_url,
                title=title,
                content=content,
                published_at=published_at,
                author=None,
                source_url=url,
                content_hash=fingerprint,
            )

        except Exception as exc:
            print(f"Error crawling {url}: {exc}")
            return None

    def crawl_source(self, start_url: str) -> list[CrawledItem]:
        """Crawl a source starting from a URL."""
        items = []
        rule = self._get_rule(start_url)

        with self._http_client() as client:
            try:
                response = client.get(
                    start_url,
                    headers={"User-Agent": self.USER_AGENT},
                    timeout=self.timeout,
                )
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "lxml")
                article_links = self._extract_article_links(soup, start_url, rule)
                print(f"Found {len(article_links)} article links on {start_url}")

                for link in article_links[:20]:
                    item = self.crawl_article(client, link)
                    if item:
                        items.append(item)

            except Exception as exc:
                print(f"Error crawling source {start_url}: {exc}")

        return items

    def crawl_feed_result(self, result: FetchLike) -> list[CrawledItem]:
        """Crawl items from a feed fetch result."""
        if is_feed_content(result.content):
            return []
        return self.crawl_source(result.url)


def crawl_non_rss_sources(results: list[FetchLike]) -> list[CrawledItem]:
    """Crawl non-RSS fetch results."""
    crawler = SmartCrawler()
    all_items = []

    for result in results:
        if result.content_type == "error" or not result.content:
            continue

        items = crawler.crawl_feed_result(result)
        all_items.extend(items)

    return all_items
