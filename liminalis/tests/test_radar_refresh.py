from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from backend.radar.extractor import ExtractedItem
from backend.radar.normalize import Normalizer
from backend.radar.refresh import (
    _filter_recent_extracted_items,
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
