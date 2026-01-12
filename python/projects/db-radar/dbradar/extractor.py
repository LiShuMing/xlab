"""Extract structured data from fetched HTML/RSS content."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import List, Optional
from urllib.parse import urlparse

import feedparser
from bs4 import BeautifulSoup
from readability import Document

from dbradar.fetcher import FetchResult


@dataclass
class ExtractedItem:
    """A single extracted news/update item."""

    url: str
    product: str
    title: str
    content: str  # Plain text content
    html_content: str  # Original HTML
    published_at: Optional[str]
    author: Optional[str]
    content_type: str  # "release", "blog", "news", "docs", "other"
    confidence: float  # 0-1, relevance confidence


class Extractor:
    """Extract structured items from fetched content."""

    # Keywords for content classification
    RELEASE_KEYWORDS = [
        "release",
        "released",
        "announcing",
        "announcement",
        "version",
        "v\d+\.",
        "changelog",
        "what's new",
    ]
    ENGINE_KEYWORDS = [
        "query",
        "execution",
        "optimizer",
        "scan",
        "join",
        "filter",
        "aggregate",
        "vectorized",
        "codegen",
        "MPP",
    ]
    PERFORMANCE_KEYWORDS = [
        "performance",
        "benchmark",
        "speed",
        "optimize",
        "fast",
        "faster",
        "latency",
        "throughput",
    ]

    def extract_rss_items(self, result: FetchResult) -> List[ExtractedItem]:
        """Extract items from RSS/Atom feeds."""
        items = []
        try:
            feed = feedparser.parse(result.content)
        except Exception:
            return items

        for entry in feed.entries:
            # Try to extract publication date
            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    published_at = dt.isoformat()
                except (ValueError, TypeError):
                    pass
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                try:
                    dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                    published_at = dt.isoformat()
                except (ValueError, TypeError):
                    pass

            # Determine content type
            content_type = self._classify_content(
                entry.get("title", ""), entry.get("summary", "")
            )

            # Get content (prefer full content if available)
            html_content = ""
            if hasattr(entry, "content") and entry.content:
                html_content = entry.content[0].value if entry.content else ""
            elif hasattr(entry, "summary"):
                html_content = entry.summary

            items.append(
                ExtractedItem(
                    url=entry.get("link", result.url),
                    product=result.product,
                    title=unescape(entry.get("title", "")).strip(),
                    content=self._html_to_text(html_content),
                    html_content=html_content,
                    published_at=published_at,
                    author=entry.get("author"),
                    content_type=content_type,
                    confidence=self._calculate_confidence(
                        entry.get("title", ""), entry.get("summary", "")
                    ),
                )
            )

        return items

    def extract_html_items(self, result: FetchResult) -> List[ExtractedItem]:
        """Extract items from HTML pages (blogs, news, docs)."""
        items = []

        try:
            doc = Document(result.content)
            title = doc.title().strip()
            main_content = doc.summary()

            soup = BeautifulSoup(main_content, "lxml")

            # Try to find article date
            published_at = self._extract_date(soup)

            # Extract links with their context
            content_type = self._classify_content(title, soup.get_text())

            # Get article text
            article_text = soup.get_text(separator=" ", strip=True)
            # Limit text length for efficiency
            article_text = article_text[:5000] if len(article_text) > 5000 else article_text

            items.append(
                ExtractedItem(
                    url=result.url,
                    product=result.product,
                    title=title,
                    content=article_text,
                    html_content=main_content,
                    published_at=published_at,
                    author=None,
                    content_type=content_type,
                    confidence=self._calculate_confidence(title, article_text),
                )
            )

            # Try to extract individual news items from list pages
            items.extend(self._extract_list_items(result, soup))

        except Exception as e:
            # Return a single error item
            items.append(
                ExtractedItem(
                    url=result.url,
                    product=result.product,
                    title=f"Error parsing: {result.url}",
                    content=str(e),
                    html_content="",
                    published_at=None,
                    author=None,
                    content_type="error",
                    confidence=0.0,
                )
            )

        return items

    def _extract_list_items(
        self, result: FetchResult, soup: BeautifulSoup
    ) -> List[ExtractedItem]:
        """Extract individual items from list pages (e.g., blog index)."""
        items = []

        # Look for common patterns in list pages
        article_tags = soup.find_all(["article", "li", "div"], class_=re.compile(r"post|article|entry|item"))
        for tag in article_tags[:10]:  # Limit to first 10 items
            link = tag.find("a", href=True)
            if not link:
                continue

            title = link.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            href = link["href"]
            if not href.startswith("http"):
                parsed = urlparse(result.url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"

            content_type = self._classify_content(title, tag.get_text())

            items.append(
                ExtractedItem(
                    url=href,
                    product=result.product,
                    title=title,
                    content=tag.get_text(separator=" ", strip=True)[:500],
                    html_content=str(tag),
                    published_at=None,
                    author=None,
                    content_type=content_type,
                    confidence=self._calculate_confidence(title, tag.get_text()),
                )
            )

        return items

    def extract(self, result: FetchResult) -> List[ExtractedItem]:
        """Extract items from a fetch result based on content type."""
        if result.content_type == "rss" or result.content_type == "error":
            # Still try to parse as HTML for error recovery
            return self.extract_html_items(result)

        if self._is_rss_content(result.content):
            return self.extract_rss_items(result)

        return self.extract_html_items(result)

    def extract_all(self, results: List[FetchResult]) -> List[ExtractedItem]:
        """Extract items from all fetch results."""
        all_items = []
        for result in results:
            items = self.extract(result)
            all_items.extend(items)
        return all_items

    def _is_rss_content(self, content: str) -> bool:
        """Check if content looks like RSS/Atom."""
        return "<rss" in content[:500] or "<feed" in content[:500] or 'xmlns="http://www.w3.org/2005/Atom' in content[:500]

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)
        return text[:3000] if len(text) > 3000 else text

    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract publication date from HTML."""
        # Try common patterns
        date_selectors = [
            ("time", {"datetime": True}),
            ("meta", {"property": "article:published_time"}),
            ("meta", {"name": "publication-date"}),
            ("span", re.compile(r"date|time|published")),
        ]

        for selector, attrs in date_selectors:
            if isinstance(selector, str) and selector == "meta":
                tag = soup.find("meta", attrs=attrs)
                if tag and tag.get("content"):
                    return tag["content"]
            else:
                tag = soup.find(selector, attrs=attrs if isinstance(attrs, dict) else {"class": attrs})
                if tag:
                    if tag.name == "time" and tag.get("datetime"):
                        return tag["datetime"]
                    text = tag.get_text(strip=True)
                    if text:
                        return text

        return None

    def _classify_content(self, title: str, content: str) -> str:
        """Classify the type of content."""
        text = f"{title} {content}".lower()

        if any(kw in text for kw in self.RELEASE_KEYWORDS):
            return "release"
        elif any(kw in text for kw in self.ENGINE_KEYWORDS):
            return "engine"
        elif any(kw in text for kw in self.PERFORMANCE_KEYWORDS):
            return "performance"
        elif "docs" in text or "documentation" in text:
            return "docs"
        elif "blog" in text or "post" in text:
            return "blog"
        else:
            return "other"

    def _calculate_confidence(self, title: str, content: str) -> float:
        """Calculate relevance confidence score (0-1)."""
        text = f"{title} {content}".lower()
        score = 0.3  # Base confidence

        # Boost for DB/OLAP related keywords
        db_keywords = [
            "database", "db", "olap", "query", "sql", "analytics",
            "storage", "index", "partition", "materialized", "view",
            "lakehouse", "warehouse", "data", "table", "column",
            "parquet", "duckdb", "clickhouse", "trino", "spark",
        ]
        score += sum(0.05 for kw in db_keywords if kw in text)

        # Boost for release/announcement content
        if any(kw in text.lower() for kw in self.RELEASE_KEYWORDS):
            score += 0.2

        # Cap at 1.0
        return min(score, 1.0)


def extract_items(results: List[FetchResult]) -> List[ExtractedItem]:
    """Convenience function to extract items from all results."""
    extractor = Extractor()
    return extractor.extract_all(results)
