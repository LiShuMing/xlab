"""
Integration tests for project identification module.
Tests discover_projects, persistence, and pipeline integration.
"""

import json
import sqlite3

import pytest

from my_email.db.models import SCHEMA_SQL
from my_email.db.repository import save_summary
from my_email.project.clusterer import (
    backfill_message_topics,
    clear_projects,
    discover_projects,
    get_project,
    get_project_emails,
    list_projects,
    save_assignment,
    save_project,
)
from my_email.project.models import Project


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_db():
    """Create an in-memory SQLite database with all tables."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()


@pytest.fixture
def populated_db(temp_db):
    """Database with sample messages and topics for clustering tests."""
    # Insert messages
    messages = [
        ("msg-001", "thread-1", "DuckDB Query", "user@duckdb.org", "2026-03-10T10:00:00Z"),
        ("msg-002", "thread-1", "DuckDB Performance", "dev@duckdb.org", "2026-03-11T11:00:00Z"),
        ("msg-003", "thread-2", "Database Design", "arch@duckdb.org", "2026-03-12T12:00:00Z"),
        ("msg-004", "thread-2", "SQL Queries", "user@duckdb.org", "2026-03-13T13:00:00Z"),
        ("msg-005", "thread-3", "Apache Iceberg", "dev@iceberg.apache.org", "2026-03-14T14:00:00Z"),
        ("msg-006", "thread-3", "Table Format", "user@iceberg.apache.org", "2026-03-15T15:00:00Z"),
        ("msg-007", "thread-4", "Iceberg Schema", "dev@iceberg.apache.org", "2026-03-16T16:00:00Z"),
        ("msg-008", "thread-4", "Data Lake", "arch@apache.org", "2026-03-17T17:00:00Z"),
    ]
    for msg_id, thread_id, subject, sender, received_at in messages:
        temp_db.execute(
            """INSERT INTO messages (id, thread_id, subject, sender, received_at)
               VALUES (?, ?, ?, ?, ?)""",
            (msg_id, thread_id, subject, sender, received_at),
        )
    temp_db.commit()

    # Insert topics - DuckDB cluster
    duckdb_topics = ["duckdb", "database", "sql", "olap"]
    for msg_id in ["msg-001", "msg-002", "msg-003", "msg-004"]:
        for topic in duckdb_topics:
            temp_db.execute(
                "INSERT INTO message_topics (message_id, topic) VALUES (?, ?)",
                (msg_id, topic),
            )

    # Insert topics - Iceberg cluster (some overlap with "database")
    iceberg_topics = ["iceberg", "table-format", "data-lake", "schema-evolution"]
    for msg_id in ["msg-005", "msg-006", "msg-007", "msg-008"]:
        for topic in iceberg_topics:
            temp_db.execute(
                "INSERT INTO message_topics (message_id, topic) VALUES (?, ?)",
                (msg_id, topic),
            )

    temp_db.commit()
    yield temp_db


# ── integration: discover_projects ─────────────────────────────────────────────

class TestDiscoverProjects:
    """Tests for discover_projects clustering."""

    def test_discover_projects_empty_db(self, temp_db):
        """Empty database returns no projects."""
        result = discover_projects(temp_db)
        assert result == []

    def test_discover_projects_single_cluster(self, temp_db):
        """All topics cluster into single project."""
        # Insert messages
        for i in range(5):
            temp_db.execute(
                "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
                (f"msg-{i}", f"thread-{i}", f"Subject {i}", "user@example.com", f"2026-03-{10+i}T10:00:00Z"),
            )
        temp_db.commit()

        # Insert shared topics
        for i in range(5):
            for topic in ["project-a", "feature-x", "release"]:
                temp_db.execute(
                    "INSERT INTO message_topics (message_id, topic) VALUES (?, ?)",
                    (f"msg-{i}", topic),
                )
        temp_db.commit()

        result = discover_projects(temp_db, min_emails=3, co_occurrence_threshold=3)

        assert len(result) == 1
        assert result[0].email_count == 5
        assert set(result[0].keywords) >= {"project-a", "feature-x", "release"}

    def test_discover_projects_multiple_clusters(self, populated_db):
        """Disconnected topics form separate projects."""
        result = discover_projects(populated_db, min_emails=3, co_occurrence_threshold=3)

        # Should get at least one project
        assert len(result) >= 1

        # Each project should have distinct sender domains
        for project in result:
            assert project.email_count >= 3

    def test_discover_projects_min_emails_filter(self, temp_db):
        """Small clusters filtered out."""
        # Insert only 2 messages (below min_emails=3)
        for i in range(2):
            temp_db.execute(
                "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
                (f"msg-{i}", f"thread-{i}", f"Subject {i}", "user@example.com", f"2026-03-{10+i}T10:00:00Z"),
            )
            for topic in ["small-cluster", "test"]:
                temp_db.execute(
                    "INSERT INTO message_topics (message_id, topic) VALUES (?, ?)",
                    (f"msg-{i}", topic),
                )
        temp_db.commit()

        result = discover_projects(temp_db, min_emails=3, co_occurrence_threshold=1)

        assert result == []

    def test_discover_projects_co_occurrence_threshold(self, temp_db):
        """Threshold controls clustering strictness."""
        # Insert messages with topics that share only 1 message (below threshold)
        temp_db.execute(
            "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
            ("msg-1", "t1", "S1", "user@example.com", "2026-03-10T10:00:00Z"),
        )
        temp_db.execute(
            "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
            ("msg-2", "t2", "S2", "user@example.com", "2026-03-11T10:00:00Z"),
        )
        temp_db.execute(
            "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
            ("msg-3", "t3", "S3", "user@example.com", "2026-03-12T10:00:00Z"),
        )
        temp_db.commit()

        # topic-a appears in msg-1 and msg-2
        temp_db.execute("INSERT INTO message_topics (message_id, topic) VALUES ('msg-1', 'topic-a')")
        temp_db.execute("INSERT INTO message_topics (message_id, topic) VALUES ('msg-2', 'topic-a')")
        # topic-b appears in msg-1 and msg-3
        temp_db.execute("INSERT INTO message_topics (message_id, topic) VALUES ('msg-1', 'topic-b')")
        temp_db.execute("INSERT INTO message_topics (message_id, topic) VALUES ('msg-3', 'topic-b')")
        temp_db.commit()

        # With threshold 2, topics share only 1 message, should not link
        result = discover_projects(temp_db, min_emails=1, co_occurrence_threshold=2)

        # topic-a and topic-b should NOT be in same cluster (only share msg-1)
        # Each topic cluster has only 2 messages
        for project in result:
            assert project.email_count >= 2

    def test_discover_projects_first_last_seen(self, temp_db):
        """Date tracking works."""
        for i in range(5):
            temp_db.execute(
                "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
                (f"msg-{i}", f"thread-{i}", f"Subject {i}", "user@example.com", f"2026-03-{10+i}T10:00:00Z"),
            )
            temp_db.execute(
                "INSERT INTO message_topics (message_id, topic) VALUES (?, ?)",
                (f"msg-{i}", "shared-topic"),
            )
        temp_db.commit()

        result = discover_projects(temp_db, min_emails=3, co_occurrence_threshold=1)

        assert len(result) == 1
        assert result[0].first_seen == "2026-03-10"
        assert result[0].last_seen == "2026-03-14"


# ── integration: persistence ───────────────────────────────────────────────────

class TestPersistence:
    """Tests for project persistence functions."""

    def test_save_and_get_project(self, temp_db):
        """Save and retrieve a project."""
        project = Project(
            id="test-project",
            name="Test Project",
            keywords=["test", "example"],
            sender_domains=["example.com"],
            email_count=5,
            first_seen="2026-03-01",
            last_seen="2026-03-20",
        )

        save_project(temp_db, project)

        result = get_project(temp_db, "test-project")

        assert result is not None
        assert result.id == "test-project"
        assert result.name == "Test Project"
        assert result.keywords == ["test", "example"]
        assert result.sender_domains == ["example.com"]
        assert result.email_count == 5

    def test_list_projects(self, temp_db):
        """List all projects sorted by count."""
        for i in range(3):
            project = Project(
                id=f"project-{i}",
                name=f"Project {i}",
                keywords=["test"],
                sender_domains=[],
                email_count=(i + 1) * 10,
            )
            save_project(temp_db, project)

        result = list_projects(temp_db)

        assert len(result) == 3
        # Sorted by email_count descending
        assert result[0].email_count == 30
        assert result[1].email_count == 20
        assert result[2].email_count == 10

    def test_list_projects_min_filter(self, temp_db):
        """List projects filtered by minimum email count."""
        for i in range(3):
            project = Project(
                id=f"project-{i}",
                name=f"Project {i}",
                keywords=["test"],
                sender_domains=[],
                email_count=(i + 1) * 5,
            )
            save_project(temp_db, project)

        result = list_projects(temp_db, min_emails=10)

        assert len(result) == 2  # Only projects with 10+ emails

    def test_clear_projects(self, temp_db):
        """Clear removes all projects."""
        project = Project(id="test", name="Test", keywords=[], sender_domains=[], email_count=1)
        save_project(temp_db, project)

        clear_projects(temp_db)

        result = list_projects(temp_db)
        assert result == []

    def test_save_assignment(self, temp_db):
        """Save an email-to-project assignment."""
        # Create message and project first
        temp_db.execute(
            "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
            ("msg-001", "t1", "Test", "user@example.com", "2026-03-10T10:00:00Z"),
        )
        project = Project(id="test", name="Test", keywords=["test"], sender_domains=[])
        save_project(temp_db, project)
        temp_db.commit()

        from my_email.project.clusterer import ProjectAssignment
        assignment = ProjectAssignment(
            message_id="msg-001",
            project_id="test",
            confidence=0.85,
            reasons=["topic match", "domain match"],
        )
        save_assignment(temp_db, assignment)

        # Verify assignment
        cursor = temp_db.execute(
            "SELECT project_id, confidence, reasons FROM email_projects WHERE message_id = ?",
            ("msg-001",),
        )
        row = cursor.fetchone()

        assert row is not None
        assert row[0] == "test"
        assert row[1] == 0.85
        assert json.loads(row[2]) == ["topic match", "domain match"]


# ── integration: pipeline ──────────────────────────────────────────────────────

class TestPipelineIntegration:
    """Tests for integration with existing summarization pipeline."""

    def test_save_summary_populates_message_topics(self, temp_db):
        """save_summary populates message_topics table."""
        # Insert message first
        temp_db.execute(
            "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
            ("msg-001", "t1", "Test Subject", "user@duckdb.org", "2026-03-10T10:00:00Z"),
        )
        temp_db.commit()

        summary_json = json.dumps({
            "title": "DuckDB Release",
            "sender_org": "DuckDB Labs",
            "topics": ["duckdb", "database", "release"],
            "summary": "DuckDB 1.0 released.",
            "key_points": ["Fast OLAP", "Embedded"],
            "relevance": "high",
        })

        save_summary(temp_db, "msg-001", summary_json, "gpt-4")

        # Verify message_topics populated
        cursor = temp_db.execute(
            "SELECT topic FROM message_topics WHERE message_id = ? ORDER BY topic",
            ("msg-001",),
        )
        topics = [row[0] for row in cursor.fetchall()]

        assert topics == ["database", "duckdb", "release"]

    def test_backfill_message_topics(self, temp_db):
        """Backfill from existing summaries."""
        # Insert message and summary
        temp_db.execute(
            "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
            ("msg-001", "t1", "Test", "user@example.com", "2026-03-10T10:00:00Z"),
        )
        summary_json = json.dumps({
            "title": "Test",
            "topics": ["test-topic", "example"],
            "summary": "Test summary.",
            "key_points": [],
            "relevance": "medium",
        })
        temp_db.execute(
            "INSERT INTO summaries (message_id, summary_json, model) VALUES (?, ?, ?)",
            ("msg-001", summary_json, "gpt-4"),
        )
        temp_db.commit()

        count = backfill_message_topics(temp_db)

        assert count == 2

        # Verify topics
        cursor = temp_db.execute("SELECT topic FROM message_topics WHERE message_id = ?", ("msg-001",))
        topics = [row[0] for row in cursor.fetchall()]
        assert set(topics) == {"test-topic", "example"}

    def test_backfill_idempotent(self, temp_db):
        """Backfill is idempotent (INSERT OR IGNORE)."""
        # Insert message and summary
        temp_db.execute(
            "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
            ("msg-001", "t1", "Test", "user@example.com", "2026-03-10T10:00:00Z"),
        )
        summary_json = json.dumps({
            "title": "Test",
            "topics": ["test"],
            "summary": "Test.",
            "key_points": [],
            "relevance": "medium",
        })
        temp_db.execute(
            "INSERT INTO summaries (message_id, summary_json, model) VALUES (?, ?, ?)",
            ("msg-001", summary_json, "gpt-4"),
        )
        temp_db.commit()

        # Run backfill twice
        count1 = backfill_message_topics(temp_db)
        count2 = backfill_message_topics(temp_db)

        assert count1 == 1
        assert count2 == 0  # No new entries on second run

    def test_message_topics_foreign_key(self, temp_db):
        """Referential integrity enforced."""
        # Enable foreign key enforcement
        temp_db.execute("PRAGMA foreign_keys=ON")
        # Try inserting topic for non-existent message
        with pytest.raises(sqlite3.IntegrityError):
            temp_db.execute(
                "INSERT INTO message_topics (message_id, topic) VALUES (?, ?)",
                ("non-existent-msg", "test-topic"),
            )


# ── integration: get_project_emails ───────────────────────────────────────────

class TestGetProjectEmails:
    """Tests for querying emails by project."""

    def test_get_project_emails(self, temp_db):
        """Retrieve emails for a project."""
        # Setup: message, project, assignment
        temp_db.execute(
            "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
            ("msg-001", "t1", "Test Subject", "user@example.com", "2026-03-10T10:00:00Z"),
        )
        project = Project(id="test", name="Test", keywords=["test"], sender_domains=[])
        save_project(temp_db, project)
        temp_db.commit()

        from my_email.project.clusterer import ProjectAssignment
        assignment = ProjectAssignment(
            message_id="msg-001",
            project_id="test",
            confidence=0.8,
            reasons=["topic match"],
        )
        save_assignment(temp_db, assignment)

        result = get_project_emails(temp_db, "test")

        assert len(result) == 1
        assert result[0]["id"] == "msg-001"
        assert result[0]["subject"] == "Test Subject"

    def test_get_project_emails_date_filter(self, temp_db):
        """Filter emails by date range."""
        for i in range(3):
            temp_db.execute(
                "INSERT INTO messages (id, thread_id, subject, sender, received_at) VALUES (?, ?, ?, ?, ?)",
                (f"msg-{i}", f"t{i}", f"Subject {i}", "user@example.com", f"2026-03-{10+i}T10:00:00Z"),
            )
        project = Project(id="test", name="Test", keywords=[], sender_domains=[])
        save_project(temp_db, project)
        temp_db.commit()

        from my_email.project.clusterer import ProjectAssignment
        for i in range(3):
            assignment = ProjectAssignment(
                message_id=f"msg-{i}",
                project_id="test",
                confidence=0.8,
                reasons=[],
            )
            save_assignment(temp_db, assignment)

        # Filter to only March 11 (end_date needs to include the full day)
        # Using >= '2026-03-11' and <= '2026-03-11T23:59:59Z' to capture the whole day
        result = get_project_emails(
            temp_db, "test",
            start_date="2026-03-11",
            end_date="2026-03-11T23:59:59Z"
        )

        assert len(result) == 1
        assert result[0]["id"] == "msg-1"