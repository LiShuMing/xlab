"""
Daily digest builder.

Aggregates all summaries for a given date into a DailyDigest:
- topic frequency ranking across all emails
- high-relevance count
- ordered list of per-email summaries

No LLM call here — pure aggregation over already-computed summaries.
"""

import json

import structlog
from pydantic import BaseModel

from my_email.db.repository import get_summaries_for_date
from my_email.llm.summarizer import EmailSummary

log = structlog.get_logger()


class TopicCluster(BaseModel):
    topic: str
    count: int
    email_titles: list[str]


class DailyDigest(BaseModel):
    date: str
    total_emails: int
    high_relevance_count: int
    top_topics: list[str]          # ranked by frequency
    topic_clusters: list[TopicCluster]
    summaries: list[dict]          # EmailSummary fields + message_id + received_at


def build_digest(db_conn, digest_date: str) -> DailyDigest:
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

    summaries: list[dict] = []
    topic_index: dict[str, list[str]] = {}  # topic → [email titles]
    high_count = 0

    for row in rows:
        data = json.loads(row["summary_json"])
        summary = EmailSummary(**data)

        if summary.relevance == "high":
            high_count += 1

        for topic in summary.topics:
            key = topic.lower().strip()
            topic_index.setdefault(key, []).append(summary.title)

        summaries.append(
            {
                **data,
                "message_id": row["message_id"],
                "received_at": row["received_at"],
            }
        )

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
        top_topics=top_topics,
        topic_clusters=topic_clusters,
        summaries=summaries,
    )

    log.info(
        "digest.built",
        date=digest_date,
        total=len(summaries),
        high=high_count,
        top_topics=top_topics[:5],
    )
    return digest
