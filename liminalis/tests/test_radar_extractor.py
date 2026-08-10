from __future__ import annotations

from backend.radar.extractor import Extractor
from backend.radar.fetcher import FetchResult
from tests.test_shared_web_feed import ATOM_FEED


def test_radar_extractor_uses_shared_article_extraction() -> None:
    long_content = " ".join(["database optimizer shared extraction"] * 30)
    result = FetchResult(
        url="https://example.test/blog/post",
        product="Example Blog",
        content=f"""
        <html>
          <head><meta name="author" content="Example Author" /></head>
          <body>
            <article>
              <h1>Shared Radar Extractor</h1>
              <time datetime="2026-02-03T00:00:00Z"></time>
              <p>{long_content}</p>
            </article>
          </body>
        </html>
        """,
        content_type="html",
        status_code=200,
    )

    items = Extractor().extract_html_items(result)

    assert items
    assert items[0].title == "Shared Radar Extractor"
    assert "database optimizer shared extraction" in items[0].content
    assert items[0].content_type == "engine"


def test_radar_extractor_detects_atom_content_even_when_content_type_is_html() -> None:
    result = FetchResult(
        url="https://example.test/updates",
        product="Example Feed",
        content=ATOM_FEED,
        content_type="html",
        status_code=200,
    )

    items = Extractor().extract(result)

    assert len(items) == 1
    assert items[0].title == "Atom Item"
    assert items[0].url == "https://example.test/atom-item"
