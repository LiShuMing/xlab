from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from tech_radar.domain import Signal


class SignalStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS signals (
                    external_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    object_type TEXT NOT NULL,
                    author TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    url TEXT NOT NULL,
                    published_at TEXT,
                    collected_at TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    media_json TEXT NOT NULL,
                    priority INTEGER NOT NULL DEFAULT 0,
                    score REAL NOT NULL,
                    annotations_json TEXT NOT NULL DEFAULT '{}',
                    raw_json TEXT NOT NULL,
                    PRIMARY KEY (platform, external_id)
                );
                CREATE TABLE IF NOT EXISTS signal_sources (
                    platform TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    PRIMARY KEY (platform, external_id, source_id),
                    FOREIGN KEY (platform, external_id)
                        REFERENCES signals(platform, external_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS deliveries (
                    publisher_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    delivered_at TEXT NOT NULL,
                    report_location TEXT NOT NULL,
                    PRIMARY KEY (publisher_id, platform, external_id),
                    FOREIGN KEY (platform, external_id)
                        REFERENCES signals(platform, external_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_signals_collected_at
                    ON signals(collected_at);
                CREATE INDEX IF NOT EXISTS idx_signals_platform_score
                    ON signals(platform, score DESC);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(signals)").fetchall()
            }
            if "priority" not in columns:
                connection.execute(
                    "ALTER TABLE signals ADD COLUMN priority INTEGER NOT NULL DEFAULT 0"
                )
            if "annotations_json" not in columns:
                connection.execute(
                    """
                    ALTER TABLE signals
                    ADD COLUMN annotations_json TEXT NOT NULL DEFAULT '{}'
                    """
                )

    def upsert_many(self, signals: Iterable[Signal]) -> tuple[int, int]:
        inserted = 0
        updated = 0
        with self._connect() as connection:
            for signal in signals:
                existing = connection.execute(
                    """
                    SELECT tags_json FROM signals
                    WHERE platform = ? AND external_id = ?
                    """,
                    (signal.platform, signal.external_id),
                ).fetchone()
                existing_tags = json.loads(existing["tags_json"]) if existing else []
                merged_tags = tuple(sorted(set(existing_tags) | set(signal.tags)))
                connection.execute(
                    """
                    INSERT INTO signals (
                        external_id, platform, object_type, author,
                        title, content, url, published_at, collected_at,
                        tags_json, metrics_json, media_json, priority, score,
                        annotations_json, raw_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(platform, external_id) DO UPDATE SET
                        author = excluded.author,
                        title = excluded.title,
                        content = excluded.content,
                        url = excluded.url,
                        published_at = excluded.published_at,
                        tags_json = excluded.tags_json,
                        metrics_json = excluded.metrics_json,
                        media_json = excluded.media_json,
                        priority = MAX(priority, excluded.priority),
                        score = MAX(score, excluded.score),
                        annotations_json = excluded.annotations_json,
                        raw_json = excluded.raw_json
                    """,
                    self._row(signal, merged_tags),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO signal_sources
                        (platform, external_id, source_id)
                    VALUES (?, ?, ?)
                    """,
                    (signal.platform, signal.external_id, signal.source_id),
                )
                if existing:
                    updated += 1
                else:
                    inserted += 1
        return inserted, updated

    def for_local_date(self, day: date, timezone_name: str) -> list[Signal]:
        zone = ZoneInfo(timezone_name)
        start = datetime.combine(day, time.min, zone).astimezone(timezone.utc)
        end = datetime.combine(day, time.max, zone).astimezone(timezone.utc)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT signals.*, GROUP_CONCAT(signal_sources.source_id, ', ') AS source_ids
                FROM signals
                LEFT JOIN signal_sources USING (platform, external_id)
                WHERE collected_at >= ? AND collected_at <= ?
                GROUP BY signals.platform, signals.external_id
                ORDER BY score DESC, published_at DESC, collected_at DESC
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall()
        return [self._signal(row) for row in rows]

    def undelivered(
        self, publisher_id: str, day: date, timezone_name: str
    ) -> list[Signal]:
        zone = ZoneInfo(timezone_name)
        end = datetime.combine(day, time.max, zone).astimezone(timezone.utc)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT signals.*, GROUP_CONCAT(signal_sources.source_id, ', ') AS source_ids
                FROM signals
                LEFT JOIN signal_sources USING (platform, external_id)
                WHERE signals.collected_at <= ?
                  AND NOT EXISTS (
                      SELECT 1 FROM deliveries
                      WHERE deliveries.publisher_id = ?
                        AND deliveries.platform = signals.platform
                        AND deliveries.external_id = signals.external_id
                  )
                GROUP BY signals.platform, signals.external_id
                ORDER BY score DESC, published_at DESC, collected_at DESC
                """,
                (end.isoformat(), publisher_id),
            ).fetchall()
        return [self._signal(row) for row in rows]

    def mark_delivered(
        self,
        publisher_id: str,
        signal_keys: Iterable[tuple[str, str]],
        report_location: str,
    ) -> None:
        delivered_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT OR IGNORE INTO deliveries (
                    publisher_id, platform, external_id,
                    delivered_at, report_location
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    (
                        publisher_id,
                        platform,
                        external_id,
                        delivered_at,
                        report_location,
                    )
                    for platform, external_id in signal_keys
                ),
            )

    def count(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) FROM signals").fetchone()
        return int(row[0])

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _row(signal: Signal, tags: tuple[str, ...]) -> tuple[object, ...]:
        return (
            signal.external_id,
            signal.platform,
            signal.object_type,
            signal.author,
            signal.title,
            signal.content,
            signal.url,
            signal.published_at,
            signal.collected_at,
            json.dumps(tags, ensure_ascii=False),
            json.dumps(signal.metrics, ensure_ascii=False, sort_keys=True),
            json.dumps(signal.media, ensure_ascii=False),
            signal.priority,
            signal.score,
            json.dumps(signal.annotations, ensure_ascii=False, sort_keys=True),
            json.dumps(signal.raw, ensure_ascii=False, sort_keys=True),
        )

    @staticmethod
    def _signal(row: sqlite3.Row) -> Signal:
        return Signal(
            source_id=row["source_ids"],
            external_id=row["external_id"],
            platform=row["platform"],
            object_type=row["object_type"],
            author=row["author"],
            title=row["title"],
            content=row["content"],
            url=row["url"],
            published_at=row["published_at"],
            collected_at=row["collected_at"],
            tags=tuple(json.loads(row["tags_json"])),
            metrics=json.loads(row["metrics_json"]),
            media=tuple(json.loads(row["media_json"])),
            priority=int(row["priority"]),
            score=float(row["score"]),
            annotations=json.loads(row["annotations_json"]),
            raw=json.loads(row["raw_json"]),
        )
