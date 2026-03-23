"""
Database layer.

Provides repositories for messages, summaries, digests, and topic tracking.
"""

from my_email.db.repository import (
    MessageData,
    get_connection,
    get_digest,
    get_summaries_for_date,
    get_sync_state,
    get_unprocessed_messages,
    init_db,
    save_digest,
    save_summary,
    save_sync_state,
    save_thread_summary,
    upsert_message,
)
from my_email.db.topic_repository import (
    TopicTrend,
    get_active_topics,
    upsert_topic_tracks,
)

__all__ = [
    "MessageData",
    "get_connection",
    "init_db",
    "upsert_message",
    "get_unprocessed_messages",
    "save_summary",
    "save_thread_summary",
    "get_summaries_for_date",
    "save_digest",
    "get_digest",
    "get_sync_state",
    "save_sync_state",
    "upsert_topic_tracks",
    "get_active_topics",
    "TopicTrend",
]
