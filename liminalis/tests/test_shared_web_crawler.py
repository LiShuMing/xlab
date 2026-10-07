from __future__ import annotations

import httpx

from backend._shared.web_crawler import ContentFingerprinter, SmartCrawler, URLNormalizer


def test_url_normalizer_removes_common_tracking_params() -> None:
    normalized = URLNormalizer.normalize("HTTPS://www.Example.test/Post?utm_source=x&keep=1#section")

    assert normalized == "https://example.test/Post?keep=1"


def test_url_normalizer_produces_stable_query_and_default_port_order() -> None:
    left = URLNormalizer.normalize("https://www.example.test:443/post?b=2&utm_id=x&a=1#top")
    right = URLNormalizer.normalize("https://example.test/post?a=1&b=2")

    assert left == right == "https://example.test/post?a=1&b=2"


def test_content_fingerprinter_matches_normalized_text() -> None:
    left = ContentFingerprinter.fingerprint("Hello,   Shared Fetcher!")
    right = ContentFingerprinter.fingerprint("hello shared fetcher")

    assert left == right
    assert ContentFingerprinter.similarity(left, right) == 1.0


def test_smart_crawler_crawls_article_with_mock_transport() -> None:
    long_content = " ".join(["Shared crawler content"] * 20)

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://example.test/blog/":
            return httpx.Response(
                200,
                text="""
                <html><body>
                  <article><a href="/blog/post-1?utm_source=newsletter">Post</a></article>
                </body></html>
                """,
            )
        if str(request.url) == "https://example.test/blog/post-1?utm_source=newsletter":
            return httpx.Response(
                200,
                text=f"""
                <html>
                  <head><link rel="canonical" href="/blog/post-1" /></head>
                  <body>
                    <article>
                      <h1>Shared crawler article</h1>
                      <time datetime="2026-01-01T00:00:00Z"></time>
                      <p>{long_content}</p>
                    </article>
                  </body>
                </html>
                """,
            )
        return httpx.Response(404)

    crawler = SmartCrawler(transport=httpx.MockTransport(handler))

    items = crawler.crawl_source("https://example.test/blog/")

    assert len(items) == 1
    assert items[0].url == "https://example.test/blog/post-1"
    assert items[0].title == "Shared crawler article"
    assert items[0].published_at == "2026-01-01T00:00:00Z"
