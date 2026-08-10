from __future__ import annotations

from backend._shared.web_cache import Cache


def test_shared_web_cache_round_trips_entry(tmp_path) -> None:
    cache = Cache(tmp_path)
    content_hash = cache.get_content_hash("hello")

    cache.set(
        url="https://example.test/feed",
        content="hello",
        content_hash=content_hash,
        etag='"abc"',
        last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
        status_code=200,
    )

    entry = cache.get("https://example.test/feed")

    assert entry is not None
    assert entry.content == "hello"
    assert entry.content_hash == content_hash
    assert entry.etag == '"abc"'
    assert cache.is_stale("https://example.test/feed") is False
    assert cache.is_stale("https://example.test/missing") is True
