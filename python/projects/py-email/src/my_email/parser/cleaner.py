"""
HTML → clean plain text conversion for email bodies.

Design notes:
- html2text handles tag stripping and markdown-like conversion.
- BeautifulSoup is used only as a pre-pass to remove known noise nodes
  (style/script/nav/footer) before handing off to html2text.
- Output is truncated at 8k chars to keep LLM prompts bounded.
  At ~4 chars/token this is ~2k tokens, well within qwen2.5 context.
"""

from __future__ import annotations

import re

import html2text
from bs4 import BeautifulSoup

# Tags to remove before text extraction
_NOISE_TAGS: list[str] = ["style", "script", "nav", "footer", "head", "noscript"]

# Maximum output length in characters
MAX_CHARS: int = 8_000

# Shared html2text converter instance
_h2t = html2text.HTML2Text()
_h2t.ignore_links = True
_h2t.ignore_images = True
_h2t.ignore_emphasis = False
_h2t.body_width = 0  # don't hard-wrap lines


def _remove_noise(html: str) -> str:
    """
    Remove noise tags from HTML.

    Args:
        html: Raw HTML string.

    Returns:
        HTML with noise tags removed.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_NOISE_TAGS):
        tag.decompose()
    return str(soup)


def _normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    - Collapses 3+ consecutive blank lines to 2
    - Strips trailing whitespace per line

    Args:
        text: Input text.

    Returns:
        Normalized text.
    """
    # Collapse 3+ consecutive blank lines → 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def _truncate(text: str, max_chars: int = MAX_CHARS) -> str:
    """
    Truncate text at a paragraph boundary if possible.

    Args:
        text: Input text.
        max_chars: Maximum characters to allow.

    Returns:
        Truncated text with marker if truncated.
    """
    if len(text) <= max_chars:
        return text
    # Try to cut at a paragraph boundary near the limit
    cut = text.rfind("\n\n", 0, max_chars)
    if cut == -1:
        cut = max_chars
    return text[:cut] + "\n\n[... truncated]"


def clean_email_body(raw: str, mime_hint: str = "") -> str:
    """
    Convert a raw email body (HTML or plain text) to clean, normalized plain text.

    Args:
        raw: Raw body string (HTML or plain text).
        mime_hint: MIME type hint, e.g. "text/html" or "text/plain".

    Returns:
        Cleaned, whitespace-normalized, truncated plain text.
    """
    if not raw:
        return ""

    is_html = mime_hint == "text/html" or "<html" in raw[:200].lower()

    if is_html:
        denoised = _remove_noise(raw)
        text = _h2t.handle(denoised)
    else:
        text = raw

    text = _normalize_whitespace(text)
    return _truncate(text)