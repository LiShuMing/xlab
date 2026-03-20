import sqlite3
from pathlib import Path

import structlog

from my_email.config import settings
from my_email.db.models import SCHEMA_SQL

log = structlog.get_logger()


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    log.info("db.initialized", path=str(settings.db_path))


# ── messages ──────────────────────────────────────────────────────────────────

def upsert_message(conn: sqlite3.Connection, msg: dict) -> bool:
    """Insert message if not already present. Returns True if newly inserted."""
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
    """Return unprocessed messages, optionally filtered to a YYYY-MM-DD date."""
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
    conn.execute(
        """INSERT OR REPLACE INTO summaries (message_id, summary_json, model)
           VALUES (?, ?, ?)""",
        (message_id, summary_json, model),
    )
    conn.execute("UPDATE messages SET processed = 1 WHERE id = ?", (message_id,))


def get_summaries_for_date(conn: sqlite3.Connection, date: str) -> list[sqlite3.Row]:
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
    conn.execute(
        "INSERT OR REPLACE INTO digests (date, digest_json) VALUES (?, ?)",
        (date, digest_json),
    )


def get_digest(conn: sqlite3.Connection, date: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM digests WHERE date = ?", (date,)
    ).fetchone()


# ── sync state ────────────────────────────────────────────────────────────────

def get_sync_state(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM sync_state WHERE id = 1").fetchone()
    return dict(row) if row else None


def save_sync_state(conn: sqlite3.Connection, history_id: str, last_sync: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO sync_state (id, history_id, last_sync) VALUES (1, ?, ?)",
        (history_id, last_sync),
    )
