"""
Database repository layer for email inbox MVP.

Provides CRUD operations for messages and settings.
All functions take an explicit sqlite3.Connection for transaction control.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timedelta
from typing import Any

import structlog

from my_email.config import settings
from my_email.db.models import SCHEMA_SQL

log = structlog.get_logger()


def get_connection() -> sqlite3.Connection:
    """
    Create database connection with WAL mode.

    Returns:
        sqlite3.Connection: Connection with Row factory configured.
    """
    conn = sqlite3.connect(settings.db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
    return conn


def init_db() -> None:
    """Initialize the database schema. Creates parent directories if needed."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        log.info("db.initialized", path=str(settings.db_path))
    finally:
        conn.close()


# ── messages ──────────────────────────────────────────────────────────────────


class MessageData(dict):
    """Typed dict for message insertion data."""

    id: str
    thread_id: str
    subject: str | None
    sender: str | None
    sender_email: str | None
    received_at: str
    body_text: str | None


def _extract_email(sender: str | None) -> str | None:
    """Extract email address from sender string like 'Name <email@example.com>'."""
    if not sender:
        return None
    match = re.search(r"<([^>]+)>", sender)
    if match:
        return match.group(1)
    # If no angle brackets, check if it looks like an email
    if "@" in sender and not sender.startswith("<"):
        # Could be just the email without name
        return sender.strip()
    return None


def upsert_message(conn: sqlite3.Connection, msg: MessageData) -> bool:
    """
    Insert a message if not already present.

    Args:
        conn: Database connection.
        msg: Message data dictionary with required keys.

    Returns:
        True if newly inserted, False if message already exists.
    """
    cur = conn.execute("SELECT 1 FROM messages WHERE id = ?", (msg["id"],))
    if cur.fetchone():
        return False

    # Extract sender_email if not provided
    sender_email = msg.get("sender_email")
    if not sender_email:
        sender_email = _extract_email(msg.get("sender"))

    conn.execute(
        """INSERT INTO messages (id, thread_id, subject, sender, sender_email, received_at, body_text)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            msg["id"],
            msg.get("thread_id"),
            msg.get("subject"),
            msg.get("sender"),
            sender_email,
            msg.get("received_at"),
            msg.get("body_text"),
        ),
    )
    return True


def get_messages(
    conn: sqlite3.Connection,
    state: str | None = None,
    relevance: str | None = None,
    days: int | None = None,
    page: int = 1,
    size: int = 50,
    current_date: str | None = None,
) -> list[sqlite3.Row]:
    """
    Fetch messages with optional filters and pagination.

    Messages are ordered by priority:
    1. Unread messages (msg_state = 'unread')
    2. High relevance messages
    3. Other messages
    Each group sorted by received_at descending.

    Args:
        conn: Database connection.
        state: Filter by msg_state ('unread', 'read', 'starred').
        relevance: Filter by relevance ('high', 'medium', 'low').
        days: Only messages from last N days.
        page: Page number (1-indexed).
        size: Page size.
        current_date: Reference date for days filter (YYYY-MM-DD).

    Returns:
        List of message rows.
    """
    conditions = []
    params: list[Any] = []

    if state:
        conditions.append("msg_state = ?")
        params.append(state)

    if relevance:
        conditions.append("relevance = ?")
        params.append(relevance)

    if days:
        ref_date = current_date or datetime.utcnow().strftime("%Y-%m-%d")
        cutoff = (
            datetime.strptime(ref_date, "%Y-%m-%d") - timedelta(days=days)
        ).strftime("%Y-%m-%d")
        conditions.append("received_at >= ?")
        params.append(cutoff)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Priority ordering: unread first, then high relevance, then by date
    offset = (page - 1) * size

    return conn.execute(
        f"""SELECT * FROM messages
           {where_clause}
           ORDER BY
             CASE msg_state WHEN 'unread' THEN 0 ELSE 1 END,
             CASE relevance WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
             received_at DESC
           LIMIT ? OFFSET ?""",
        params + [size, offset],
    ).fetchall()


def get_message_by_id(conn: sqlite3.Connection, message_id: str) -> sqlite3.Row | None:
    """
    Fetch a single message by ID.

    Args:
        conn: Database connection.
        message_id: Gmail message ID.

    Returns:
        Message row with body_text, or None if not found.
    """
    return conn.execute(
        "SELECT * FROM messages WHERE id = ?", (message_id,)
    ).fetchone()


def update_message_state(
    conn: sqlite3.Connection, message_id: str, new_state: str
) -> bool:
    """
    Update the msg_state of a message.

    Args:
        conn: Database connection.
        message_id: Gmail message ID.
        new_state: New state ('read' or 'starred').

    Returns:
        True if updated, False if message not found.
    """
    cur = conn.execute(
        "UPDATE messages SET msg_state = ? WHERE id = ?", (new_state, message_id)
    )
    return cur.rowcount > 0


def get_message_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """
    Get message counts for display.

    Args:
        conn: Database connection.

    Returns:
        Dict with 'total', 'unread', 'high_relevance' counts.
    """
    total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    unread = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE msg_state = 'unread'"
    ).fetchone()[0]
    high_relevance = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE relevance = 'high'"
    ).fetchone()[0]

    return {"total": total, "unread": unread, "high_relevance": high_relevance}


def cleanup_old_messages(
    conn: sqlite3.Connection,
    retention_days: int = 7,
    current_date: str | None = None,
) -> int:
    """
    Delete messages older than retention period.

    Args:
        conn: Database connection.
        retention_days: Number of days to keep.
        current_date: Reference date (YYYY-MM-DD), defaults to today.

    Returns:
        Number of deleted messages.
    """
    ref_date = current_date or datetime.utcnow().strftime("%Y-%m-%d")
    cutoff = (
        datetime.strptime(ref_date, "%Y-%m-%d") - timedelta(days=retention_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    cur = conn.execute(
        "DELETE FROM messages WHERE received_at < ?", (cutoff,)
    )
    return cur.rowcount


def save_summary(
    conn: sqlite3.Connection, message_id: str, summary_json: str
) -> None:
    """
    Save AI summary for a message and extract relevance.

    Args:
        conn: Database connection.
        message_id: Gmail message ID.
        summary_json: Serialized summary JSON.
    """
    relevance = None
    try:
        summary_data = json.loads(summary_json)
        relevance = summary_data.get("relevance")
    except (json.JSONDecodeError, TypeError):
        log.warning(
            "repository.save_summary.parse_error",
            message_id=message_id,
        )

    conn.execute(
        "UPDATE messages SET summary_json = ?, relevance = ? WHERE id = ?",
        (summary_json if relevance else None, relevance, message_id),
    )


# ── settings ──────────────────────────────────────────────────────────────────


def get_setting(
    conn: sqlite3.Connection, key: str, default: str | None = None
) -> str | None:
    """
    Get a setting value.

    Args:
        conn: Database connection.
        key: Setting key.
        default: Default value if not found.

    Returns:
        Setting value or default.
    """
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def save_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """
    Save or update a setting.

    Args:
        conn: Database connection.
        key: Setting key.
        value: Setting value.
    """
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )