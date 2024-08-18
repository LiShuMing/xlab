"""Tests for database repository layer."""

import sqlite3

import pytest

from my_email.db.models import SCHEMA_SQL
from my_email.db.repository import (
    MessageData,
    cleanup_old_messages,
    get_message_by_id,
    get_message_counts,
    get_messages,
    get_setting,
    save_setting,
    save_summary,
    update_message_state,
    upsert_message,
)


@pytest.fixture
def db():
    """Create in-memory test database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()


class TestUpsertMessage:
    """Tests for upsert_message function."""

    def test_inserts_new_message(self, db):
        """Insert a new message."""
        msg = MessageData(
            id="msg-001",
            thread_id="thread-001",
            subject="Test Subject",
            sender="User <user@example.com>",
            sender_email="user@example.com",
            received_at="2026-03-24T10:00:00Z",
            body_text="Test body",
        )
        result = upsert_message(db, msg)
        assert result is True

        row = db.execute("SELECT * FROM messages WHERE id = ?", ("msg-001",)).fetchone()
        assert row["subject"] == "Test Subject"
        assert row["msg_state"] == "unread"

    def test_skips_duplicate(self, db):
        """Skip if message already exists."""
        msg = MessageData(id="msg-001", thread_id="t1", received_at="2026-03-24T10:00:00Z")
        upsert_message(db, msg)
        result = upsert_message(db, msg)
        assert result is False

    def test_extracts_sender_email(self, db):
        """Extract sender_email from sender field if not provided."""
        msg = MessageData(
            id="msg-002",
            thread_id="t1",
            sender="John Doe <john@example.com>",
            received_at="2026-03-24T10:00:00Z",
        )
        upsert_message(db, msg)

        row = db.execute("SELECT sender_email FROM messages WHERE id = 'msg-002'").fetchone()
        assert row["sender_email"] == "john@example.com"


class TestGetMessages:
    """Tests for get_messages function."""

    def test_ordered_by_priority(self, db):
        """Messages ordered: unread first, then high relevance, then by date."""
        db.execute(
            """INSERT INTO messages (id, thread_id, subject, received_at, msg_state, relevance)
               VALUES ('msg-1', 't1', 'Read low', '2026-03-24T12:00:00Z', 'read', 'low')"""
        )
        db.execute(
            """INSERT INTO messages (id, thread_id, subject, received_at, msg_state, relevance)
               VALUES ('msg-2', 't1', 'Unread high', '2026-03-24T10:00:00Z', 'unread', 'high')"""
        )
        db.execute(
            """INSERT INTO messages (id, thread_id, subject, received_at, msg_state, relevance)
               VALUES ('msg-3', 't1', 'Unread medium', '2026-03-24T11:00:00Z', 'unread', 'medium')"""
        )

        messages = get_messages(db)
        assert messages[0]["id"] == "msg-2"  # unread + high
        assert messages[1]["id"] == "msg-3"  # unread + medium
        assert messages[2]["id"] == "msg-1"  # read

    def test_filter_by_state(self, db):
        """Filter messages by state."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at, msg_state)
               VALUES ('msg-1', 't1', '2026-03-24T10:00:00Z', 'unread')"""
        )
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at, msg_state)
               VALUES ('msg-2', 't1', '2026-03-24T10:00:00Z', 'read')"""
        )

        messages = get_messages(db, state="unread")
        assert len(messages) == 1
        assert messages[0]["id"] == "msg-1"

    def test_filter_by_relevance(self, db):
        """Filter messages by relevance."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at, relevance)
               VALUES ('msg-1', 't1', '2026-03-24T10:00:00Z', 'high')"""
        )
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at, relevance)
               VALUES ('msg-2', 't1', '2026-03-24T10:00:00Z', 'low')"""
        )

        messages = get_messages(db, relevance="high")
        assert len(messages) == 1
        assert messages[0]["id"] == "msg-1"

    def test_filter_by_days(self, db):
        """Filter messages by days."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at)
               VALUES ('msg-1', 't1', '2026-03-20T10:00:00Z')"""
        )
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at)
               VALUES ('msg-2', 't1', '2026-03-24T10:00:00Z')"""
        )

        messages = get_messages(db, days=3, current_date="2026-03-24")
        assert len(messages) == 1
        assert messages[0]["id"] == "msg-2"

    def test_pagination(self, db):
        """Paginate results."""
        for i in range(10):
            db.execute(
                f"""INSERT INTO messages (id, thread_id, received_at)
                    VALUES ('msg-{i}', 't1', '2026-03-24T10:00:00Z')"""
            )

        page1 = get_messages(db, page=1, size=5)
        assert len(page1) == 5

        page2 = get_messages(db, page=2, size=5)
        assert len(page2) == 5


class TestGetMessageById:
    """Tests for get_message_by_id function."""

    def test_returns_message_with_body(self, db):
        """Get single message with body text."""
        db.execute(
            """INSERT INTO messages (id, thread_id, subject, body_text, received_at)
               VALUES ('msg-1', 't1', 'Test', 'Body content', '2026-03-24T10:00:00Z')"""
        )

        msg = get_message_by_id(db, "msg-1")
        assert msg is not None
        assert msg["body_text"] == "Body content"

    def test_returns_none_if_not_found(self, db):
        """Return None if message not found."""
        msg = get_message_by_id(db, "nonexistent")
        assert msg is None


class TestUpdateMessageState:
    """Tests for update_message_state function."""

    def test_updates_state(self, db):
        """Update message state."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at)
               VALUES ('msg-1', 't1', '2026-03-24T10:00:00Z')"""
        )
        update_message_state(db, "msg-1", "read")
        row = db.execute("SELECT msg_state FROM messages WHERE id = 'msg-1'").fetchone()
        assert row["msg_state"] == "read"

    def test_returns_false_if_not_found(self, db):
        """Return False if message not found."""
        result = update_message_state(db, "nonexistent", "read")
        assert result is False


class TestSettings:
    """Tests for settings functions."""

    def test_get_setting_default(self, db):
        """Get setting with default value."""
        value = get_setting(db, "nonexistent", default="default_value")
        assert value == "default_value"

    def test_save_and_get_setting(self, db):
        """Save and retrieve setting."""
        save_setting(db, "test_key", "test_value")
        value = get_setting(db, "test_key")
        assert value == "test_value"

    def test_update_existing_setting(self, db):
        """Update existing setting."""
        save_setting(db, "retention_days", "14")
        value = get_setting(db, "retention_days")
        assert value == "14"


class TestCleanupOldMessages:
    """Tests for cleanup_old_messages function."""

    def test_deletes_old_messages(self, db):
        """Delete messages older than retention days."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at)
               VALUES ('old', 't1', '2026-03-01T10:00:00Z')"""
        )
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at)
               VALUES ('new', 't1', '2026-03-24T10:00:00Z')"""
        )

        deleted = cleanup_old_messages(db, retention_days=7, current_date="2026-03-24")
        assert deleted == 1

        remaining = db.execute("SELECT id FROM messages").fetchall()
        assert len(remaining) == 1
        assert remaining[0]["id"] == "new"

    def test_keeps_all_if_within_retention(self, db):
        """Keep all messages if within retention."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at)
               VALUES ('msg-1', 't1', '2026-03-23T10:00:00Z')"""
        )

        deleted = cleanup_old_messages(db, retention_days=7, current_date="2026-03-24")
        assert deleted == 0


class TestGetMessageCounts:
    """Tests for get_message_counts function."""

    def test_returns_counts(self, db):
        """Get message counts."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at, msg_state, relevance)
               VALUES ('msg-1', 't1', '2026-03-24T10:00:00Z', 'read', 'low')"""
        )
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at, msg_state, relevance)
               VALUES ('msg-2', 't1', '2026-03-24T10:00:00Z', 'unread', 'high')"""
        )
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at, msg_state, relevance)
               VALUES ('msg-3', 't1', '2026-03-24T10:00:00Z', 'unread', 'medium')"""
        )

        counts = get_message_counts(db)
        assert counts["total"] == 3
        assert counts["unread"] == 2
        assert counts["high_relevance"] == 1


class TestSaveSummary:
    """Tests for save_summary function."""

    def test_saves_summary_and_relevance(self, db):
        """Save summary and extract relevance."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at)
               VALUES ('msg-1', 't1', '2026-03-24T10:00:00Z')"""
        )

        summary_json = '{"summary": "Test summary", "relevance": "high", "key_points": ["point1"]}'
        save_summary(db, "msg-1", summary_json)

        row = db.execute(
            "SELECT summary_json, relevance FROM messages WHERE id = 'msg-1'"
        ).fetchone()
        assert row["summary_json"] == summary_json
        assert row["relevance"] == "high"

    def test_handles_invalid_json(self, db):
        """Save summary with invalid JSON logs warning but doesn't crash."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at)
               VALUES ('msg-1', 't1', '2026-03-24T10:00:00Z')"""
        )

        # Should not raise
        save_summary(db, "msg-1", "not valid json")

        row = db.execute("SELECT summary_json FROM messages WHERE id = 'msg-1'").fetchone()
        assert row["summary_json"] is None

    def test_handles_missing_relevance(self, db):
        """Handle summary without relevance field."""
        db.execute(
            """INSERT INTO messages (id, thread_id, received_at)
               VALUES ('msg-1', 't1', '2026-03-24T10:00:00Z')"""
        )

        summary_json = '{"summary": "Test summary"}'
        save_summary(db, "msg-1", summary_json)

        row = db.execute("SELECT relevance FROM messages WHERE id = 'msg-1'").fetchone()
        assert row["relevance"] is None
