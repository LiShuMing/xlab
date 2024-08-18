"""
Topic arc tracking repository.

Two tables:
  topic_daily  — per-day mention counts (source of truth, idempotent via INSERT OR REPLACE)
  topic_tracks — lifetime aggregate per topic (recomputed from topic_daily on each upsert)

Idempotency: calling upsert_topic_tracks() twice for the same date produces the same result.
total_mentions is always SUM(topic_daily.count) — never incremented in place.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date as Date, timedelta
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from my_email.digest.builder import TopicCluster

log = structlog.get_logger()


def upsert_topic_tracks(
    conn: sqlite3.Connection,
    digest_date: str,
    topic_clusters: list[TopicCluster],
) -> None:
    """
    Persist topic arc data for a given digest date.

    Uses cluster.topic directly — already lowercase-normalized by build_digest().
    Safe to call multiple times for the same date (idempotent).

    Args:
        conn: Database connection. Must remain open for the duration of the call.
        digest_date: YYYY-MM-DD date string for the digest.
        topic_clusters: List of TopicCluster objects from DailyDigest.

    Note:
        Must be called before conn.close() as it requires an active transaction.
    """
    if not topic_clusters:
        return

    for cluster in topic_clusters:
        topic = cluster.topic
        count = cluster.count
        titles = cluster.email_titles

        # Step 1: upsert topic_daily (fully idempotent — replaces the row)
        conn.execute(
            "INSERT OR REPLACE INTO topic_daily (topic, date, count) VALUES (?, ?, ?)",
            (topic, digest_date, count),
        )

        # Step 2: recompute aggregates from topic_daily
        total = (
            conn.execute("SELECT SUM(count) FROM topic_daily WHERE topic = ?", (topic,)).fetchone()[
                0
            ]
            or 0
        )

        peak_row = conn.execute(
            "SELECT date, count FROM topic_daily WHERE topic = ? ORDER BY count DESC, date DESC LIMIT 1",
            (topic,),
        ).fetchone()
        peak_date = peak_row[0]
        peak_count = peak_row[1]

        # Step 3: get existing sample_titles (preserve prior titles on update)
        existing = conn.execute(
            "SELECT sample_titles FROM topic_tracks WHERE topic = ?", (topic,)
        ).fetchone()

        prior_titles: list[str] = json.loads(existing[0]) if existing else []

        # Append first new title (if any), keep last 3
        if titles:
            prior_titles.append(titles[0])
        sample_titles = json.dumps(prior_titles[-3:])

        # Step 4: upsert topic_tracks — first_seen_date is preserved on conflict
        conn.execute(
            """
            INSERT INTO topic_tracks
                (topic, first_seen_date, last_seen_date, total_mentions,
                 peak_date, peak_count, sample_titles)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(topic) DO UPDATE SET
                last_seen_date  = excluded.last_seen_date,
                total_mentions  = excluded.total_mentions,
                peak_date       = excluded.peak_date,
                peak_count      = excluded.peak_count,
                sample_titles   = excluded.sample_titles
            """,
            (topic, digest_date, digest_date, total, peak_date, peak_count, sample_titles),
        )

    log.info("topic_tracks.upserted", date=digest_date, count=len(topic_clusters))


class TopicTrend:
    """Type definition for topic trend data."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.topic: str = data["topic"]
        self.first_seen_date: str = data["first_seen_date"]
        self.last_seen_date: str = data["last_seen_date"]
        self.total_mentions: int = data["total_mentions"]
        self.peak_date: str = data["peak_date"]
        self.peak_count: int = data["peak_count"]
        self.sample_titles: list[str] = data["sample_titles"]
        self.trend_arrow: str = data["trend_arrow"]
        self.days_active: int = data["days_active"]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for backward compatibility."""
        return {
            "topic": self.topic,
            "first_seen_date": self.first_seen_date,
            "last_seen_date": self.last_seen_date,
            "total_mentions": self.total_mentions,
            "peak_date": self.peak_date,
            "peak_count": self.peak_count,
            "sample_titles": self.sample_titles,
            "trend_arrow": self.trend_arrow,
            "days_active": self.days_active,
        }


def get_active_topics(
    conn: sqlite3.Connection,
    as_of_date: str,
    window_days: int = 30,
    top_n: int = 20,
) -> list[dict[str, Any]]:
    """
    Return topics seen within the last window_days days, ordered by total_mentions DESC.

    Args:
        conn: Database connection.
        as_of_date: YYYY-MM-DD reference date string.
        window_days: Look-back window in days (default 30).
        top_n: Maximum number of topics to return (default 20).

    Returns:
        List of dicts containing:
          - topic: The topic string
          - first_seen_date: YYYY-MM-DD when first observed
          - last_seen_date: YYYY-MM-DD when last observed
          - total_mentions: Lifetime mention count
          - peak_date: Date with highest single-day count
          - peak_count: Highest single-day count
          - sample_titles: Last 3 email titles (list[str])
          - trend_arrow: '↑' | '→' | '↓' based on recent activity
          - days_active: Number of days between first and last seen
    """
    as_of = Date.fromisoformat(as_of_date)
    window_start = (as_of - timedelta(days=window_days - 1)).isoformat()

    rows = conn.execute(
        """
        SELECT topic, first_seen_date, last_seen_date, total_mentions,
               peak_date, peak_count, sample_titles
        FROM topic_tracks
        WHERE last_seen_date >= ?
        ORDER BY total_mentions DESC
        LIMIT ?
        """,
        (window_start, top_n),
    ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        topic = row["topic"]

        # Trend: compare last 3 days vs prior 3 days
        recent_start = (as_of - timedelta(days=2)).isoformat()
        prior_end = (as_of - timedelta(days=3)).isoformat()
        prior_start = (as_of - timedelta(days=5)).isoformat()

        recent_count = conn.execute(
            "SELECT COALESCE(SUM(count), 0) FROM topic_daily WHERE topic = ? AND date BETWEEN ? AND ?",
            (topic, recent_start, as_of_date),
        ).fetchone()[0]

        prior_count = conn.execute(
            "SELECT COALESCE(SUM(count), 0) FROM topic_daily WHERE topic = ? AND date BETWEEN ? AND ?",
            (topic, prior_start, prior_end),
        ).fetchone()[0]

        if prior_count == 0:
            trend_arrow = "→"
        elif recent_count > prior_count * 1.5:
            trend_arrow = "↑"
        elif recent_count < prior_count * 0.5:
            trend_arrow = "↓"
        else:
            trend_arrow = "→"

        first_seen = Date.fromisoformat(row["first_seen_date"])
        last_seen = Date.fromisoformat(row["last_seen_date"])
        days_active = (last_seen - first_seen).days + 1

        results.append(
            {
                "topic": topic,
                "first_seen_date": row["first_seen_date"],
                "last_seen_date": row["last_seen_date"],
                "total_mentions": row["total_mentions"],
                "peak_date": row["peak_date"],
                "peak_count": row["peak_count"],
                "sample_titles": json.loads(row["sample_titles"]),
                "trend_arrow": trend_arrow,
                "days_active": days_active,
            }
        )

    return results
