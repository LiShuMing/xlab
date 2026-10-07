from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest

from backend.radar.db_models import RadarItem
from backend.radar.identity import canonicalize_radar_url, deduplicate_radar_items, radar_item_id
from backend.radar.service import upsert_radar_item


class _EmptyResult:
    def scalar_one_or_none(self) -> None:
        return None


class _FakeSession:
    def __init__(self, existing: RadarItem | None = None) -> None:
        self.existing = existing
        self.added: list[RadarItem] = []
        self.requested_ids: list[str] = []

    async def get(self, _model: type[RadarItem], _item_id: str) -> RadarItem | None:
        self.requested_ids.append(_item_id)
        if self.existing and _item_id == self.existing.id:
            return self.existing
        return None

    async def execute(self, _statement: Any) -> _EmptyResult:
        return _EmptyResult()

    def add(self, item: RadarItem) -> None:
        self.added.append(item)


def test_radar_identity_uses_canonical_url() -> None:
    tracked = "HTTPS://www.Example.test:443/post?utm_source=mail&b=2&a=1#section"
    clean = "https://example.test/post?a=1&b=2"

    assert canonicalize_radar_url(tracked) == clean
    assert radar_item_id(tracked) == radar_item_id(clean)


def test_deduplicate_radar_items_merges_canonical_duplicates() -> None:
    items = [
        {
            "id": "old-a",
            "url": "https://www.example.test/post?utm_source=feed",
            "title": "Example",
            "summary": "",
            "tags": ["database"],
            "sources": [],
        },
        {
            "id": "old-b",
            "url": "https://example.test/post",
            "title": "Example",
            "summary": "Useful summary",
            "tags": ["olap"],
            "sources": ["feed"],
        },
    ]

    result = deduplicate_radar_items(items)

    assert len(result) == 1
    assert result[0]["url"] == "https://example.test/post"
    assert result[0]["summary"] == "Useful summary"
    assert result[0]["tags"] == ["database", "olap"]


@pytest.mark.asyncio
async def test_upsert_uses_stable_id_for_new_item() -> None:
    session = _FakeSession()

    item = await upsert_radar_item(
        session,  # type: ignore[arg-type]
        {
            "id": "legacy-id",
            "url": "https://www.example.test/post?utm_source=mail",
            "title": "Example",
            "fetched_at": datetime(2026, 3, 29, tzinfo=UTC),
        },
    )

    assert item.id == radar_item_id("https://example.test/post")
    assert item.url == "https://example.test/post"
    assert session.added == [item]


@pytest.mark.asyncio
async def test_upsert_does_not_erase_existing_enrichment_with_empty_values() -> None:
    url = "https://example.test/post"
    existing = RadarItem(
        id="different-id",
        url=url,
        title="Existing title",
        original_title="Original title",
        published_date=date(2026, 3, 20),
        product="ExampleDB",
        content_type="paper",
        summary="Existing summary",
        tags=["database"],
        sources=["feed"],
        fetched_at=datetime(2026, 3, 29, tzinfo=UTC),
        raw_content="Existing body",
        sync_batch=date(2026, 3, 29),
    )
    session = _FakeSession(existing)

    item = await upsert_radar_item(
        session,  # type: ignore[arg-type]
        {
            "id": "different-id",
            "url": "https://www.example.test/post?utm_campaign=repeat",
            "summary": "",
            "raw_content": "",
            "tags": ["olap"],
            "published_date": "0001-01-01",
        },
    )

    assert item is existing
    assert session.requested_ids == [radar_item_id(url), "different-id"]
    assert item.summary == "Existing summary"
    assert item.raw_content == "Existing body"
    assert item.content_type == "paper"
    assert item.published_date == date(2026, 3, 20)
    assert item.tags == ["database", "olap"]
