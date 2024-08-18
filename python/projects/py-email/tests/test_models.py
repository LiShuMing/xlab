"""Tests for database schema."""

import sqlite3

from my_email.db.models import MIGRATION_SQL, SCHEMA_SQL


def test_schema_creates_messages_table():
    """Verify messages table has all required columns."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)

    cursor = conn.execute("PRAGMA table_info(messages)")
    columns = {row[1] for row in cursor.fetchall()}

    required = {
        "id",
        "thread_id",
        "subject",
        "sender",
        "sender_email",
        "received_at",
        "body_text",
        "msg_state",
        "relevance",
        "summary_json",
        "created_at",
    }
    assert required.issubset(columns), f"Missing columns: {required - columns}"


def test_schema_creates_settings_table():
    """Verify settings table exists."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
    assert cursor.fetchone() is not None


def test_messages_table_indexes():
    """Verify messages table has required indexes."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indexes = {row[0] for row in cursor.fetchall()}

    required = {"idx_messages_received", "idx_messages_state", "idx_messages_relevance"}
    assert required.issubset(indexes), f"Missing indexes: {required - indexes}"


def test_settings_default_values():
    """Verify settings table has default values."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)

    cursor = conn.execute("SELECT key, value FROM settings ORDER BY key")
    rows = {row[0]: row[1] for row in cursor.fetchall()}

    assert rows.get("retention_days") == "7"
    assert rows.get("auto_sync_interval_minutes") == "30"
    assert rows.get("last_history_id") == ""


def test_messages_msg_state_default():
    """Verify messages.msg_state defaults to 'unread'."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)

    # Insert without specifying msg_state
    conn.execute(
        """INSERT INTO messages (id, thread_id, received_at)
           VALUES ('test-id', 'thread-1', '2026-03-24T10:00:00Z')"""
    )

    cursor = conn.execute("SELECT msg_state FROM messages WHERE id = 'test-id'")
    row = cursor.fetchone()
    assert row[0] == "unread"


def test_old_tables_dropped():
    """Verify old tables are dropped using MIGRATION_SQL."""
    conn = sqlite3.connect(":memory:")
    # Create old tables first
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE summaries (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE digests (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE topic_daily (topic TEXT)")
    conn.execute("CREATE TABLE topic_tracks (topic TEXT)")
    conn.execute("CREATE TABLE message_topics (message_id TEXT)")
    conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE email_projects (message_id TEXT)")
    conn.execute("CREATE TABLE sync_state (id INTEGER PRIMARY KEY)")

    # Now run the migration SQL which drops old tables
    conn.executescript(MIGRATION_SQL)
    # Then run the new schema
    conn.executescript(SCHEMA_SQL)

    # Verify old tables don't exist
    old_tables = [
        "summaries",
        "digests",
        "topic_daily",
        "topic_tracks",
        "message_topics",
        "projects",
        "email_projects",
        "sync_state",
    ]
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ("
        + ",".join("?" * len(old_tables))
        + ")",
        old_tables,
    )
    remaining = cursor.fetchall()
    assert len(remaining) == 0, f"Old tables still exist: {remaining}"
