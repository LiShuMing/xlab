"""Shared web article extraction helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

import trafilatura
from bs4 import BeautifulSoup
from readability import Document


@dataclass(frozen=True)
class ArticleExtraction:
    """Normalized article extraction result."""

    title: str
    text: str
    html: str
    published_at: str | None = None
    author: str | None = None
    engine: str = "fallback"


def clean_text(text: str, max_chars: int | None = None) -> str:
    """Normalize whitespace and optionally truncate text."""
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if max_chars is not None and len(normalized) > max_chars:
        return normalized[:max_chars]
    return normalized


def html_to_text(html: str, max_chars: int | None = None) -> str:
    """Convert HTML to plain text with boilerplate tags removed."""
    if not html:
        return ""

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return clean_text(soup.get_text(separator=" ", strip=True), max_chars=max_chars)


def extract_article(
    html: str,
    *,
    url: str | None = None,
    max_chars: int = 5000,
    min_chars: int = 80,
) -> ArticleExtraction | None:
    """Extract article text and metadata from an HTML document.

    Trafilatura is tried first for robust boilerplate removal and metadata
    extraction. Readability remains the fallback because it is lightweight and
    already matches the historical Radar behavior.
    """
    if not html:
        return None

    extracted = _extract_with_trafilatura(html, url=url, max_chars=max_chars)
    if extracted and len(extracted.text) >= min_chars:
        return extracted

    return _extract_with_readability(html, max_chars=max_chars, min_chars=min_chars)


def _extract_with_trafilatura(html: str, *, url: str | None, max_chars: int) -> ArticleExtraction | None:
    try:
        extracted = trafilatura.bare_extraction(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
            with_metadata=True,
        )
    except Exception:
        return None

    if not extracted:
        return None
    data = extracted.as_dict()

    text = clean_text(str(data.get("text") or data.get("raw_text") or ""), max_chars=max_chars)
    title = clean_text(str(data.get("title") or ""))
    if not text:
        return None

    return ArticleExtraction(
        title=title,
        text=text,
        html=html,
        published_at=data.get("date"),
        author=data.get("author"),
        engine="trafilatura",
    )


def _extract_with_readability(html: str, *, max_chars: int, min_chars: int) -> ArticleExtraction | None:
    try:
        doc = Document(html)
        title = clean_text(doc.title())
        main_content = doc.summary()
        text = html_to_text(main_content, max_chars=max_chars)
    except Exception:
        return None

    if not title and not text:
        return None
    if len(text) < min_chars:
        return None

    soup = BeautifulSoup(main_content, "lxml")
    return ArticleExtraction(
        title=title,
        text=text,
        html=main_content,
        published_at=extract_date_from_html(soup),
        author=None,
        engine="readability",
    )


def extract_date_from_html(soup: BeautifulSoup) -> str | None:
    """Extract a publication date from common HTML metadata patterns."""
    tag = soup.find("time", datetime=True)
    if tag:
        return tag["datetime"]

    for meta_attrs in [
        {"property": "article:published_time"},
        {"name": "publication-date"},
        {"name": "date"},
    ]:
        tag = soup.find("meta", attrs=meta_attrs)
        if tag and tag.get("content"):
            return tag["content"]

    tag = soup.find(["span", "div", "p"], class_=re.compile(r"date|time|published", re.I))
    if tag:
        text = tag.get_text(strip=True)
        if text:
            return text

    return None
