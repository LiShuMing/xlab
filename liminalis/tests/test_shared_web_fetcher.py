from __future__ import annotations

import httpx

from backend._shared.web_cache import Cache
from backend._shared.web_fetcher import FetchTarget, WebFetcher
from tests.test_shared_web_feed import RSS10_FEED


def test_shared_web_fetcher_fetches_and_reuses_conditional_cache(tmp_path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.headers.get("if-none-match") == '"abc"':
            return httpx.Response(304)
        return httpx.Response(200, text="<rss>ok</rss>", headers={"ETag": '"abc"'})

    fetcher = WebFetcher(
        cache=Cache(tmp_path),
        transport=httpx.MockTransport(handler),
        enable_http_cache=False,
    )
    target = FetchTarget(
        url="https://example.test/feed.xml",
        product="Example",
        filter_tags=["release"],
        assume_rss=True,
    )

    first = fetcher.fetch_target(target, use_cache=False)
    second = fetcher.fetch_target(target, use_cache=False)

    assert first.content == "<rss>ok</rss>"
    assert first.is_cached is False
    assert second.is_cached is True
    assert second.status_code == 304
    assert second.filter_tags == ["release"]
    assert requests[1].headers["if-none-match"] == '"abc"'


def test_shared_web_fetcher_returns_fresh_cache_without_network(tmp_path) -> None:
    cache = Cache(tmp_path)
    cache.set(
        url="https://example.test/article",
        content="<html>cached</html>",
        content_hash=cache.get_content_hash("<html>cached</html>"),
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("fresh cache should avoid network")

    fetcher = WebFetcher(
        cache=cache,
        transport=httpx.MockTransport(handler),
        enable_http_cache=False,
    )

    result = fetcher.fetch_target(
        FetchTarget(url="https://example.test/article", product="Example"),
        use_cache=True,
    )

    assert result.is_cached is True
    assert result.content == "<html>cached</html>"
    assert result.content_type == "html"


def test_shared_web_fetcher_classifies_feed_content_without_feed_url(tmp_path) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=RSS10_FEED)

    fetcher = WebFetcher(
        cache=Cache(tmp_path),
        transport=httpx.MockTransport(handler),
        enable_http_cache=False,
    )

    result = fetcher.fetch_target(
        FetchTarget(url="https://example.test/updates", product="Example"),
        use_cache=False,
    )

    assert result.content_type == "rss"
