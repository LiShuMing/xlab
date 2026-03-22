"""Content normalization service: HTML/Markdown to clean NormalizedDoc."""

import re

import markdownify
from bs4 import BeautifulSoup

from pia.models.source_doc import NormalizedDoc
from pia.utils.hashing import hash_content


class NormalizeService:
    """Converts raw HTML or markdown content into a clean NormalizedDoc.

    Removes navigation, sidebars, footers, ads, and other noise elements
    before converting to clean markdown suitable for LLM analysis.
    """

    REMOVE_TAGS = ["nav", "header", "footer", "aside", "script", "style", "noscript"]
    REMOVE_CLASSES = [
        "sidebar",
        "navigation",
        "nav",
        "toc",
        "breadcrumb",
        "footer",
        "cookie",
        "banner",
        "ad",
        "advertisement",
    ]

    def normalize_html(self, html: str, source_url: str = "") -> NormalizedDoc:
        """Parse and clean an HTML page, returning a NormalizedDoc.

        Removes navigation and noise elements, extracts headings and links,
        then converts the main content area to markdown.

        Args:
            html: Raw HTML string.
            source_url: Source URL for attribution metadata.

        Returns:
            NormalizedDoc with clean markdown body and extracted metadata.
        """
        soup = BeautifulSoup(html, "lxml")

        # Remove noise elements by tag
        for tag in self.REMOVE_TAGS:
            for el in soup.find_all(tag):
                el.decompose()

        # Remove noise elements by class name
        for cls in self.REMOVE_CLASSES:
            for el in soup.find_all(class_=re.compile(cls, re.I)):
                el.decompose()

        # Extract title
        title = ""
        if soup.title:
            title = soup.title.get_text(strip=True)
        elif h1 := soup.find("h1"):
            title = h1.get_text(strip=True)

        # Extract headings
        headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"])]

        # Extract external links
        links = [
            a.get("href", "")
            for a in soup.find_all("a", href=True)
            if str(a.get("href", "")).startswith("http")
        ]

        # Find main content area
        main = (
            soup.find("main")
            or soup.find("article")
            or soup.find(class_=re.compile(r"content|main|body", re.I))
            or soup.body
            or soup
        )

        md = markdownify.markdownify(str(main), heading_style="ATX", bullets="-")
        # Clean up excessive blank lines
        md = re.sub(r"\n{3,}", "\n\n", md).strip()

        return NormalizedDoc(
            title=title,
            published_at=None,
            headings=headings,
            markdown_body=md,
            extracted_links=list(set(links))[:50],
            content_hash=hash_content(md),
            source_url=source_url,
        )

    def normalize_markdown(self, content: str, source_url: str = "") -> NormalizedDoc:
        """Process content that is already in markdown format.

        Useful for GitHub release bodies which are already markdown.

        Args:
            content: Markdown string.
            source_url: Source URL for attribution metadata.

        Returns:
            NormalizedDoc wrapping the markdown content.
        """
        lines = content.split("\n")
        headings = [line.lstrip("#").strip() for line in lines if line.startswith("#")]
        links = re.findall(r"https?://[^\s\)\"\'>\]]+", content)
        title = headings[0] if headings else ""
        # Clean up excessive blank lines
        md = re.sub(r"\n{3,}", "\n\n", content).strip()

        return NormalizedDoc(
            title=title,
            published_at=None,
            headings=headings,
            markdown_body=md,
            extracted_links=list(set(links))[:50],
            content_hash=hash_content(md),
            source_url=source_url,
        )
