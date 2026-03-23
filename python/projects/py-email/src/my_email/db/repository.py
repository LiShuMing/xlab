"""
Database repository layer.

Provides low-level CRUD operations for messages, summaries, digests, and sync state.
All functions take an explicit sqlite3.Connection for transaction control.
"""

import sqlite3
from typing import Any

import structlog

from my_email.config import settings
from my_email.db.models import SCHEMA_SQL

log = structlog.get_logger()


def get_connection() -> sqlite3.Connection:
    """
    Create a new database connection with WAL mode and foreign keys enabled.

    Returns:
        sqlite3.Connection: Connection with Row factory configured.
    """
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Initialize the database schema. Creates parent directories if needed."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    log.info("db.initialized", path=str(settings.db_path))


# ── messages ──────────────────────────────────────────────────────────────────

class MessageData(dict):
    """Typed dict for message insertion data."""
    id: str
    thread_id: str
    subject: str | None
    sender: str | None
    received_at: str
    labels: str | None
    body_text: str | None


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
    conn.execute(
        """INSERT INTO messages (id, thread_id, subject, sender, received_at, labels, body_text)
           VALUES (:id, :thread_id, :subject, :sender, :received_at, :labels, :body_text)""",
        msg,
    )
    return True


def get_unprocessed_messages(
    conn: sqlite3.Connection, date: str | None = None
) -> list[sqlite3.Row]:
    """
    Fetch unprocessed messages, optionally filtered by date.

    Args:
        conn: Database connection.
        date: Optional YYYY-MM-DD date filter.

    Returns:
        List of message rows ordered by received_at.
    """
    if date:
        return conn.execute(
            "SELECT * FROM messages WHERE processed = 0 AND received_at LIKE ? ORDER BY received_at",
            (f"{date}%",),
        ).fetchall()
    return conn.execute(
        "SELECT * FROM messages WHERE processed = 0 ORDER BY received_at"
    ).fetchall()


# ── summaries ─────────────────────────────────────────────────────────────────

def save_summary(
    conn: sqlite3.Connection, message_id: str, summary_json: str, model: str
) -> None:
    """
    Save a message summary and mark the message as processed.

    Args:
        conn: Database connection.
        message_id: Gmail message ID.
        summary_json: Serialized EmailSummary JSON.
        model: LLM model identifier.
    """
    conn.execute(
        """INSERT OR REPLACE INTO summaries (message_id, summary_json, model)
           VALUES (?, ?, ?)""",
        (message_id, summary_json, model),
    )
    conn.execute("UPDATE messages SET processed = 1 WHERE id = ?", (message_id,))


def save_thread_summary(
    conn: sqlite3.Connection,
    message_ids: list[str],
    summary_json: str,
    model: str,
) -> None:
    """
    Save a thread summary and mark all messages as processed.

    Stores the summary against the first message ID and marks all
    provided message IDs as processed.

    Args:
        conn: Database connection.
        message_ids: List of Gmail message IDs in the thread.
        summary_json: Serialized EmailSummary JSON.
        model: LLM model identifier.
    """
    if not message_ids:
        return

    # Store summary against first message
    first_id = message_ids[0]
    conn.execute(
        """INSERT OR REPLACE INTO summaries (message_id, summary_json, model)
           VALUES (?, ?, ?)""",
        (first_id, summary_json, model),
    )

    # Mark all messages in the thread as processed
    placeholders = ",".join("?" * len(message_ids))
    conn.execute(
        f"UPDATE messages SET processed = 1 WHERE id IN ({placeholders})",
        message_ids,
    )


def get_summaries_for_date(conn: sqlite3.Connection, date: str) -> list[sqlite3.Row]:
    """
    Fetch all summaries for a given date with message metadata.

    Args:
        conn: Database connection.
        date: YYYY-MM-DD date string.

    Returns:
        List of summary rows joined with message metadata.
    """
    return conn.execute(
        """SELECT s.id, s.message_id, s.summary_json, s.model, s.created_at,
                  m.subject, m.sender, m.received_at
           FROM summaries s
           JOIN messages m ON m.id = s.message_id
           WHERE m.received_at LIKE ?
           ORDER BY m.received_at""",
        (f"{date}%",),
    ).fetchall()


# ── digests ───────────────────────────────────────────────────────────────────

def save_digest(conn: sqlite3.Connection, date: str, digest_json: str) -> None:
    """
    Save a daily digest.

    Args:
        conn: Database connection.
        date: YYYY-MM-DD date string.
        digest_json: Serialized DailyDigest JSON.
    """
    conn.execute(
        "INSERT OR REPLACE INTO digests (date, digest_json) VALUES (?, ?)",
        (date, digest_json),
    )


def get_digest(conn: sqlite3.Connection, date: str) -> sqlite3.Row | None:
    """
    Fetch a digest by date.

    Args:
        conn: Database connection.
        date: YYYY-MM-DD date string.

    Returns:
        Digest row or None if not found.
    """
    return conn.execute(
        "SELECT * FROM digests WHERE date = ?", (date,)
    ).fetchone()


# ── sync state ────────────────────────────────────────────────────────────────

def get_sync_state(conn: sqlite3.Connection) -> dict[str, Any] | None:
    """
    Get the current Gmail sync state.

    Args:
        conn: Database connection.

    Returns:
        Dict with history_id and last_sync, or None if no state.
    """
    row = conn.execute("SELECT * FROM sync_state WHERE id = 1").fetchone()
    return dict(row) if row else None


def save_sync_state(conn: sqlite3.Connection, history_id: str, last_sync: str) -> None:
    """
    Save the Gmail sync state.

    Args:
        conn: Database connection.
        history_id: Gmail history ID for incremental sync.
        last_sync: ISO-8601 UTC timestamp of last sync.
    """
    conn.execute(
        "INSERT OR REPLACE INTO sync_state (id, history_id, last_sync) VALUES (1, ?, ?)",
        (history_id, last_sync),
    )