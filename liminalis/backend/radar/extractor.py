"""Extract structured data from fetched HTML/RSS content."""

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from backend._shared.content import classify_content, relevance_confidence
from backend._shared.web_extract import extract_article, extract_date_from_html, html_to_text
from backend._shared.web_feed import is_feed_content, parse_feed_content
from backend.radar.fetcher import FetchResult


@dataclass
class ExtractedItem:
    """A single extracted news/update item."""

    url: str
    product: str
    title: str
    content: str  # Plain text content
    html_content: str  # Original HTML
    published_at: str | None
    author: str | None
    content_type: str  # "release", "blog", "news", "docs", "other"
    confidence: float  # 0-1, relevance confidence


class Extractor:
    """Extract structured items from fetched content."""

    def extract_rss_items(self, result: FetchResult) -> list[ExtractedItem]:
        """Extract items from RSS/Atom feeds."""
        items = []
        try:
            feed = parse_feed_content(result.content)
        except Exception:
            return items

        for entry in feed.entries:
            # Try to extract publication date
            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    dt = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                    published_at = dt.isoformat()
                except (ValueError, TypeError):
                    pass
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                try:
                    dt = datetime(*entry.updated_parsed[:6], tzinfo=UTC)
                    published_at = dt.isoformat()
                except (ValueError, TypeError):
                    pass

            # Determine content type
            content_type = self._classify_content(entry.get("title", ""), entry.get("summary", ""))

            # Get content (prefer full content if available)
            html_content = ""
            if hasattr(entry, "content") and entry.content:
                html_content = entry.content[0].value if entry.content else ""
            elif hasattr(entry, "summary"):
                html_content = entry.summary

            # Get the link and ensure it's absolute
            link = entry.get("link", result.url)
            # Resolve relative URLs against the feed URL
            if link.startswith("/"):
                link = urljoin(result.url, link)

            items.append(
                ExtractedItem(
                    url=link,
                    product=result.product,
                    title=unescape(entry.get("title", "")).strip(),
                    content=self._html_to_text(html_content),
                    html_content=html_content,
                    published_at=published_at,
                    author=entry.get("author"),
                    content_type=content_type,
                    confidence=self._calculate_confidence(entry.get("title", ""), entry.get("summary", "")),
                )
            )

        return items

    def extract_html_items(self, result: FetchResult) -> list[ExtractedItem]:
        """Extract items from HTML pages (blogs, news, docs)."""
        items = []

        try:
            article = extract_article(result.content, url=result.url)
            if article is None:
                raise ValueError("Unable to extract article content")

            title = article.title
            published_at = article.published_at
            article_text = article.text
            content_type = self._classify_content(title, article_text)

            items.append(
                ExtractedItem(
                    url=result.url,
                    product=result.product,
                    title=title,
                    content=article_text,
                    html_content=article.html,
                    published_at=published_at,
                    author=article.author,
                    content_type=content_type,
                    confidence=self._calculate_confidence(title, article_text),
                )
            )

            # Try to extract individual news items from list pages
            items.extend(self._extract_list_items(result, BeautifulSoup(result.content, "lxml")))

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

    def _extract_list_items(self, result: FetchResult, soup: BeautifulSoup) -> list[ExtractedItem]:
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
            # Resolve relative URLs properly
            if not href.startswith(("http://", "https://")):
                href = urljoin(result.url, href)

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

    def extract(self, result: FetchResult) -> list[ExtractedItem]:
        """Extract items from a fetch result based on content type."""
        if result.content_type == "error" or not result.content:
            return []

        if result.content_type == "rss" or self._is_rss_content(result.content):
            return self.extract_rss_items(result)

        return self.extract_html_items(result)

    def extract_all(self, results: list[FetchResult]) -> list[ExtractedItem]:
        """Extract items from all fetch results."""
        all_items = []
        for result in results:
            items = self.extract(result)
            all_items.extend(items)
        return all_items

    def _is_rss_content(self, content: str) -> bool:
        """Check if content looks like RSS/Atom."""
        return is_feed_content(content)

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        if not html:
            return ""
        return html_to_text(html, max_chars=3000)

    def _extract_date(self, soup: BeautifulSoup) -> str | None:
        """Extract publication date from HTML."""
        return extract_date_from_html(soup)

    def _classify_content(self, title: str, content: str) -> str:
        """Classify the type of content."""
        return classify_content(title, content)

    def _calculate_confidence(self, title: str, content: str) -> float:
        """Calculate relevance confidence score (0-1)."""
        return relevance_confidence(title, content)


def extract_items(results: list[FetchResult]) -> list[ExtractedItem]:
    """Convenience function to extract items from all results."""
    extractor = Extractor()
    return extractor.extract_all(results)


def extract_items_from_enhanced(enhanced_items: list) -> list[ExtractedItem]:
    """Convert EnhancedItem objects from external APIs to ExtractedItem."""
    items = []
    for ei in enhanced_items:
        # Determine content type based on snippet
        extractor = Extractor()
        content_type = extractor._classify_content(ei.title, ei.snippet)
        confidence = extractor._calculate_confidence(ei.title, ei.snippet)

        items.append(
            ExtractedItem(
                url=ei.url,
                product=ei.product,
                title=ei.title,
                content=ei.snippet,
                html_content="",
                published_at=ei.published_at,
                author=None,
                content_type=content_type,
                confidence=confidence,
            )
        )
    return items
