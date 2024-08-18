"""
HTML digest renderer.

Converts a DailyDigest + active_topics list into a self-contained HTML string.
Template is loaded from the package directory (no CDN dependencies).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

from my_email.digest.builder import DailyDigest

log = structlog.get_logger()

_TEMPLATE_DIR = Path(__file__).parent / "templates"


class TemplateError(RuntimeError):
    """Raised when HTML template cannot be loaded."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        super().__init__(message)
        self.original_error = original_error


def build_html_digest(digest: DailyDigest, active_topics: list[dict[str, Any]]) -> str:
    """
    Render the digest as a self-contained HTML string.

    Args:
        digest: DailyDigest from build_digest().
        active_topics: List of topic dicts from get_active_topics() — may be empty.

    Returns:
        Self-contained HTML string ready for browser display.

    Raises:
        TemplateError: If Jinja2 is not installed or template is missing.

    Note:
        Jinja2 autoescape is enabled to prevent XSS attacks from user content.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, TemplateNotFound
    except ImportError as exc:
        raise TemplateError(
            "jinja2 is required for HTML output. Install with: pip install jinja2",
            exc,
        ) from exc

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=True,  # Security: prevent XSS from user content
    )

    try:
        template = env.get_template("digest.html.j2")
    except TemplateNotFound as exc:
        raise TemplateError(
            f"HTML template not found at {_TEMPLATE_DIR / 'digest.html.j2'}. "
            "Was the package installed correctly? Check pyproject.toml package-data.",
            exc,
        ) from exc

    html = template.render(
        digest=digest,
        summaries=digest.summaries,
        active_topics=active_topics,
    )

    log.info(
        "renderer.html_built",
        date=digest.date,
        emails=digest.total_emails,
        active_topics=len(active_topics),
        html_bytes=len(html.encode()),
    )
    return html
