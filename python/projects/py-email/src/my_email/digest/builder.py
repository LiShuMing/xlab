"""
Daily digest builder.

Aggregates all summaries for a given date into a DailyDigest:
- topic frequency ranking across all emails
- high-relevance count
- ordered list of per-email summaries

No LLM call here — pure aggregation over already-computed summaries.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any

import structlog
from pydantic import BaseModel

from my_email.db.repository import get_summaries_for_date
from my_email.llm.summarizer import EmailSummary

log = structlog.get_logger()


class TopicCluster(BaseModel):
    """A topic cluster with its frequency and associated email titles."""

    topic: str
    count: int
    email_titles: list[str]


class DailyDigest(BaseModel):
    """Daily digest containing aggregated email summaries and topic analysis."""

    date: str
    total_emails: int
    high_relevance_count: int
    skipped_count: int = 0  # Non-technical emails filtered out
    top_topics: list[str]
    topic_clusters: list[TopicCluster]
    summaries: list[dict[str, Any]]


def build_digest(db_conn: sqlite3.Connection, digest_date: str) -> DailyDigest:
    """
    Build a daily digest from summarized messages.

    Aggregates topic frequencies and ranks them across all emails for the date.
    Pure aggregation — no LLM calls.
    Filters out non-technical emails (relevance="skip").

    Args:
        db_conn: Database connection.
        digest_date: YYYY-MM-DD date string.

    Returns:
        DailyDigest with topic rankings and ordered summaries.
    """
    rows = get_summaries_for_date(db_conn, digest_date)

    if not rows:
        log.warning("digest.no_summaries", date=digest_date)
        return DailyDigest(
            date=digest_date,
            total_emails=0,
            high_relevance_count=0,
            top_topics=[],
            topic_clusters=[],
            summaries=[],
        )

    summaries: list[dict[str, Any]] = []
    skipped_count = 0
    topic_index: dict[str, list[str]] = {}
    high_count = 0

    for row in rows:
        data = json.loads(row["summary_json"])
        summary = EmailSummary(**data)

        # Skip non-technical emails
        if summary.relevance == "skip":
            skipped_count += 1
            log.debug("digest.skipped_non_technical", title=summary.title[:50])
            continue

        if summary.relevance == "high":
            high_count += 1

        for topic in summary.topics:
            key = topic.lower().strip()
            topic_index.setdefault(key, []).append(summary.title)

        summaries.append({
            **data,
            "message_id": row["message_id"],
            "received_at": row["received_at"],
        })

    # Rank topics by frequency (descending), cap at 15
    ranked = sorted(topic_index.items(), key=lambda x: len(x[1]), reverse=True)[:15]
    top_topics = [t for t, _ in ranked]
    topic_clusters = [
        TopicCluster(topic=t, count=len(titles), email_titles=titles)
        for t, titles in ranked
    ]

    digest = DailyDigest(
        date=digest_date,
        total_emails=len(summaries),
        high_relevance_count=high_count,
        skipped_count=skipped_count,
        top_topics=top_topics,
        topic_clusters=topic_clusters,
        summaries=summaries,
    )

    log.info(
        "digest.built",
        date=digest_date,
        total=len(summaries),
        skipped=skipped_count,
        high=high_count,
        top_topics=top_topics[:5],
    )
    return digest