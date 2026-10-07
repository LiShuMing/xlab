from __future__ import annotations

from datetime import date, datetime

from backend.radar.identity import radar_item_id
from backend.radar.legacy import build_legacy_dataset


def test_legacy_dataset_merges_overlaps_without_losing_enrichment() -> None:
    rows = [
        {
            "id": "old-a",
            "url": "https://www.example.test/post?utm_source=feed",
            "title": "Original",
            "summary": "Useful summary",
            "tags": ["database"],
            "published_date": date(2026, 3, 20),
            "fetched_at": datetime(2026, 3, 21),
        },
        {
            "id": "old-b",
            "url": "https://example.test/post",
            "title": "Updated",
            "summary": "",
            "tags": ["olap"],
            "published_date": date(1, 1, 1),
            "fetched_at": datetime(2026, 3, 22),
        },
    ]

    dataset = build_legacy_dataset(rows)

    assert dataset.summary() == {
        "files": 0,
        "inputRows": 2,
        "items": 1,
        "duplicateRows": 1,
        "invalidRows": 0,
    }
    item = dataset.items[0]
    assert item["id"] == radar_item_id("https://example.test/post")
    assert item["title"] == "Updated"
    assert item["summary"] == "Useful summary"
    assert item["tags"] == ["database", "olap"]
    assert item["published_date"] == date(2026, 3, 20)
    assert item["legacy_ids"] == ["old-a", "old-b"]
