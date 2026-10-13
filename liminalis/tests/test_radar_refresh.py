from __future__ import annotations

import json
import os
import threading
import time
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.radar.cache import Cache
from backend.radar.extractor import ExtractedItem
from backend.radar.feeds import FeedSource
from backend.radar.fetcher import Fetcher
from backend.radar.normalize import Normalizer
from backend.radar.refresh import (
    _acquire_refresh_lock,
    _enrich_with_full_articles,
    _filter_recent_extracted_items,
    _merge_incremental_items,
    _ranked_item_to_data,
    get_radar_refresh_status,
    load_radar_artifact,
    refresh_latest_radar_news,
    schedule_startup_radar_refresh,
)
from backend.services.radar_service import merge_radar_payloads
from backend.settings import Settings


def test_default_radar_feed_file_is_packaged() -> None:
    settings = Settings(_env_file=None)

    assert settings.radar_feeds_file.is_file()
    feeds = json.loads(settings.radar_feeds_file.read_text(encoding="utf-8"))
    assert len(feeds) >= 5
    assert all({"product", "channel", "source_id", "authority"}.issubset(feed) for feed in feeds)


def test_ranked_item_conversion_produces_api_and_upsert_shape() -> None:
    normalized = SimpleNamespace(
        url="https://example.test/post",
        title="Database update",
        product="ExampleDB",
        published_at="2026-08-23T10:00:00+00:00",
        content_type="release",
        content="A useful database release summary.",
        sources=["https://example.test/post"],
    )

    item = _ranked_item_to_data(SimpleNamespace(item=normalized))

    assert item["publishedDate"] == "2026-08-23"
    assert item["contentType"] == "release"
    assert item["summary"] == "A useful database release summary."
    assert item["rawContent"] == normalized.content
    assert item["analysisProvider"] == "extractive"
    assert item["contentHash"]


def test_feed_fetcher_runs_requests_concurrently_and_preserves_order(monkeypatch, tmp_path) -> None:
    fetcher = Fetcher(cache=Cache(tmp_path), max_workers=4)
    feeds = [
        FeedSource(title=f"Feed {index}", url=f"https://example.test/{index}", product="DB")
        for index in range(4)
    ]
    thread_ids: set[int] = set()

    def fake_fetch(_client, url, *, product, filter_tags, assume_rss, **metadata):
        thread_ids.add(threading.get_ident())
        time.sleep(0.02)
        from backend.radar.fetcher import FetchResult

        return FetchResult(
            url=url,
            product=product,
            content="<rss/>",
            content_type="rss",
            status_code=200,
            filter_tags=filter_tags,
            **metadata,
        )

    monkeypatch.setattr(fetcher, "_http_client", lambda: nullcontext(object()))
    monkeypatch.setattr(fetcher, "_fetch_single", fake_fetch)

    results = fetcher.fetch_feeds(feeds, use_cache=True)

    assert [result.url for result in results] == [feed.url for feed in feeds]
    assert len(thread_ids) > 1


def test_incremental_artifact_keeps_recent_items_from_failed_source() -> None:
    today = datetime.now(UTC).date().isoformat()
    current = [{"url": "https://example.test/new", "publishedDate": today, "score": 1.0}]
    previous = [
        {"url": "https://example.test/old", "publishedDate": today, "score": 0.5},
        {"url": "https://example.test/stale", "publishedDate": "2020-01-01", "score": 2.0},
    ]

    result = _merge_incremental_items(current, previous, max_days=7)

    assert [item["url"] for item in result] == [
        "https://example.test/new",
        "https://example.test/old",
    ]


def test_full_article_enrichment_replaces_short_feed_summary() -> None:
    from backend.radar.fetcher import FetchResult

    item = ExtractedItem(
        url="https://example.test/article",
        product="ExampleDB",
        title="ExampleDB 2.0 released",
        content="Short feed summary",
        html_content="",
        published_at="2026-10-13T00:00:00+00:00",
        author=None,
        content_type="release",
        confidence=0.8,
    )
    body = " ".join(["optimizer storage execution improvement"] * 40)

    class FakeFetcher:
        def fetch_targets_concurrent(self, _targets, *, use_cache):
            assert use_cache is True
            return [
                FetchResult(
                    url=item.url,
                    product=item.product,
                    content=f"<article><h1>{item.title}</h1><p>{body}</p></article>",
                    content_type="html",
                    status_code=200,
                )
            ]

    result = _enrich_with_full_articles([item], fetcher=FakeFetcher(), limit=1)

    assert len(result[0].content) > len("Short feed summary")
    assert "optimizer" in result[0].tags


def test_unchanged_feed_still_reuses_article_http_cache() -> None:
    item = ExtractedItem(
        url="https://example.test/article",
        product="ExampleDB",
        title="ExampleDB update",
        content="Unchanged summary",
        html_content="",
        published_at="2026-10-13T00:00:00+00:00",
        author=None,
        content_type="blog",
        confidence=0.8,
        feed_hash="same-hash",
    )

    class FakeFetcher:
        def fetch_targets_concurrent(self, targets, *, use_cache):
            assert [target.url for target in targets] == [item.url]
            assert use_cache is True
            return []

    result = _enrich_with_full_articles(
        [item],
        fetcher=FakeFetcher(),
        limit=1,
        previous_items=[{"url": item.url, "feedHash": "same-hash"}],
    )

    assert result[0].content == "Unchanged summary"


def test_filter_recent_items_before_similarity_deduplication() -> None:
    def extracted(product: str, published_at: str | None, confidence: float = 0.9) -> ExtractedItem:
        return ExtractedItem(
            url=f"https://example.test/{product}/{published_at}",
            product=product,
            title="Database update",
            content="Content",
            html_content="",
            published_at=published_at,
            author=None,
            content_type="release",
            confidence=confidence,
        )

    now = datetime.now(UTC)
    recent = extracted("RecentDB", (now - timedelta(days=1)).isoformat())
    old = extracted("OldDB", (now - timedelta(days=30)).isoformat())
    undated = [extracted("NoDateDB", None) for _ in range(4)]
    low_confidence = extracted("LowConfidenceDB", None, confidence=0.7)

    result = _filter_recent_extracted_items(
        [recent, old, *undated, low_confidence],
        Normalizer(),
        max_days=7,
    )

    assert recent in result
    assert old not in result
    assert sum(item.product == "NoDateDB" for item in result) == 3
    assert low_confidence not in result


def test_merge_radar_payloads_deduplicates_refreshed_items() -> None:
    refreshed = {
        "generatedAt": "2026-08-23T10:00:00+00:00",
        "latestSyncBatch": "2026-08-23",
        "items": [
            {
                "id": "new",
                "url": "https://www.example.test/post?utm_source=rss",
                "title": "Database update",
                "product": "ExampleDB",
                "contentType": "release",
                "summary": "Fresh summary",
                "tags": [],
                "sources": [],
            }
        ],
    }
    snapshot = {
        "sourceTotalItems": 1621,
        "latestSyncBatch": "2026-03-29",
        "items": [
            {
                "id": "old",
                "url": "https://example.test/post",
                "title": "Database update",
                "product": "ExampleDB",
                "contentType": "release",
                "summary": "",
                "tags": ["database"],
                "sources": [],
            }
        ],
    }

    result = merge_radar_payloads(refreshed, snapshot)

    assert result["totalItems"] == 1
    assert result["sourceTotalItems"] == 1621
    assert result["items"][0]["summary"] == "Fresh summary"
    assert result["items"][0]["tags"] == ["database"]


def test_disabled_startup_refresh_does_not_create_task(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        radar_refresh_on_startup=False,
        _env_file=None,
    )

    assert schedule_startup_radar_refresh(settings) is None
    assert get_radar_refresh_status()["state"] == "disabled"


def test_refresh_lock_allows_only_one_process(tmp_path) -> None:
    path = tmp_path / "refresh.lock"
    first = _acquire_refresh_lock(path, stale_after_seconds=30)
    try:
        assert first is not None
        assert _acquire_refresh_lock(path, stale_after_seconds=30) is None
    finally:
        if first is not None:
            os.close(first)
        path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_refresh_writes_local_artifact_without_postgres(monkeypatch, tmp_path) -> None:
    from backend.radar import refresh

    async def run_inline(function, *args):
        return function(*args)

    item = {
        "id": "item-1",
        "url": "https://example.test/post",
        "title": "Database update",
        "originalTitle": "Database update",
        "publishedDate": "2026-08-23",
        "product": "ExampleDB",
        "contentType": "release",
        "summary": "Fresh summary",
        "tags": [],
        "sources": [],
        "fetchedAt": datetime(2026, 8, 23, tzinfo=UTC),
        "rawContent": "Raw feed body",
        "syncBatch": "2026-08-23",
    }
    monkeypatch.setattr(refresh, "_collect_latest_news", lambda _settings: ([item], 1, 1))
    monkeypatch.setattr(refresh.asyncio, "to_thread", run_inline)
    settings = Settings(
        data_dir=tmp_path,
        pgsql_url=None,
        pgsql_host=None,
        pgsql_user=None,
        pgsql_password=None,
        _env_file=None,
    )

    result = await refresh_latest_radar_news(settings)
    artifact = load_radar_artifact(settings)

    assert result["state"] == "completed"
    assert result["storage"] == "local-artifact"
    assert artifact["totalItems"] == 1
    assert artifact["items"][0]["title"] == "Database update"
    assert "rawContent" not in artifact["items"][0]
