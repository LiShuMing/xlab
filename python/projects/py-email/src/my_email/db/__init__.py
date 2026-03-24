"""
Database layer for email inbox MVP.

Provides repository for messages and settings.
"""

from my_email.db.repository import (
    MessageData,
    cleanup_old_messages,
    get_connection,
    get_message_by_id,
    get_message_counts,
    get_messages,
    get_setting,
    init_db,
    save_setting,
    save_summary,
    update_message_state,
    upsert_message,
)

__all__ = [
    "MessageData",
    "cleanup_old_messages",
    "get_connection",
    "get_message_by_id",
    "get_message_counts",
    "get_messages",
    "get_setting",
    "init_db",
    "save_setting",
    "save_summary",
    "update_message_state",
    "upsert_message",
]