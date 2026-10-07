from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from tech_radar.domain import Signal
from tech_radar.storage import SignalStore


def signal(source: str, tags: tuple[str, ...]) -> Signal:
    return Signal(
        external_id="same-tweet",
        source_id=source,
        platform="twitter",
        object_type="timeline",
        author="alice",
        title="C++ database update",
        content="C++ database update",
        url="https://x.com/alice/status/same-tweet",
        published_at=None,
        collected_at="2026-10-06T16:30:00+00:00",
        tags=tags,
        priority=100 if source == "following" else 20,
        score=12.0,
        annotations={"topic": "数据库与查询引擎"},
    )


class SignalStoreTest(unittest.TestCase):
    def test_global_dedup_preserves_sources_and_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = SignalStore(Path(temporary_directory) / "radar.sqlite3")
            store.initialize()
            self.assertEqual((1, 1), store.upsert_many([
                signal("following", ("x",)),
                signal("database-search", ("database",)),
            ]))

            items = store.for_local_date(date(2026, 10, 7), "Asia/Shanghai")

            self.assertEqual(1, store.count())
            self.assertEqual(1, len(items))
            self.assertEqual({"database", "x"}, set(items[0].tags))
            self.assertEqual(100, items[0].priority)
            self.assertEqual("数据库与查询引擎", items[0].annotations["topic"])
            self.assertEqual(
                {"following", "database-search"},
                set(items[0].source_id.split(", ")),
            )

            unseen = store.undelivered("daily", date(2026, 10, 7), "Asia/Shanghai")
            self.assertEqual(1, len(unseen))
            store.mark_delivered(
                "daily",
                [(unseen[0].platform, unseen[0].external_id)],
                "/tmp/report.md",
            )
            self.assertEqual(
                [], store.undelivered("daily", date(2026, 10, 7), "Asia/Shanghai")
            )


if __name__ == "__main__":
    unittest.main()
