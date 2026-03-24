"""
Unit tests for project identification module.
Tests _slugify helper and assign_email scoring logic.
"""

import json
import sqlite3

import pytest

from my_email.db.models import SCHEMA_SQL
from my_email.project.clusterer import _slugify, assign_email
from my_email.project.models import Project


# ── unit: _slugify ─────────────────────────────────────────────────────────────

def test_slugify_basic():
    """Basic lowercase conversion."""
    assert _slugify("DuckDB") == "duckdb"


def test_slugify_special_chars():
    """Special characters become hyphens."""
    assert _slugify("REST API!") == "rest-api"


def test_slugify_multiple_spaces():
    """Multiple spaces collapse to single hyphen."""
    assert _slugify("Apache  Iceberg") == "apache-iceberg"


def test_slugify_leading_trailing():
    """Leading/trailing hyphens stripped."""
    assert _slugify("-Leading Hyphen-") == "leading-hyphen"


def test_slugify_empty():
    """Empty string returns empty."""
    assert _slugify("") == ""


def test_slugify_only_special():
    """Only special characters returns empty."""
    assert _slugify("!!!") == ""


# ── unit: assign_email (requires in-memory SQLite) ─────────────────────────────


@pytest.fixture
def temp_db():
    """Create an in-memory SQLite database with project tables."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()


@pytest.fixture
def sample_project():
    """Sample project for testing."""
    return Project(
        id="duckdb",
        name="DuckDB",
        keywords=["duckdb", "database"],
        sender_domains=["duckdb.org"],
        email_count=10,
        first_seen="2026-03-01",
        last_seen="2026-03-20",
    )


class TestAssignEmail:
    """Tests for assign_email scoring logic."""

    def test_assign_email_topic_match(self, temp_db, sample_project):
        """Topic overlap contributes to score."""
        # Insert sample project
        temp_db.execute(
            """INSERT INTO projects (id, name, keywords, sender_domains, email_count, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sample_project.id,
                sample_project.name,
                json.dumps(sample_project.keywords),
                json.dumps(sample_project.sender_domains),
                sample_project.email_count,
                sample_project.first_seen,
                sample_project.last_seen,
            ),
        )
        temp_db.commit()

        result = assign_email(
            conn=temp_db,
            message_id="msg-001",
            topics=["duckdb"],
            sender="user@example.com",
            min_confidence=0.3,
        )

        assert result is not None
        assert result.project_id == "duckdb"
        assert result.confidence >= 0.3
        assert "topics" in str(result.reasons).lower()

    def test_assign_email_domain_match(self, temp_db, sample_project):
        """Domain match contributes to score."""
        temp_db.execute(
            """INSERT INTO projects (id, name, keywords, sender_domains, email_count, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sample_project.id,
                sample_project.name,
                json.dumps(sample_project.keywords),
                json.dumps(sample_project.sender_domains),
                sample_project.email_count,
                sample_project.first_seen,
                sample_project.last_seen,
            ),
        )
        temp_db.commit()

        result = assign_email(
            conn=temp_db,
            message_id="msg-002",
            topics=[],
            sender="user@duckdb.org",
            min_confidence=0.3,
        )

        assert result is not None
        assert result.project_id == "duckdb"
        assert result.confidence == 0.4
        assert "domain" in str(result.reasons).lower()

    def test_assign_email_combined_score(self, temp_db, sample_project):
        """Both factors combine."""
        temp_db.execute(
            """INSERT INTO projects (id, name, keywords, sender_domains, email_count, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sample_project.id,
                sample_project.name,
                json.dumps(sample_project.keywords),
                json.dumps(sample_project.sender_domains),
                sample_project.email_count,
                sample_project.first_seen,
                sample_project.last_seen,
            ),
        )
        temp_db.commit()

        result = assign_email(
            conn=temp_db,
            message_id="msg-003",
            topics=["duckdb"],
            sender="user@duckdb.org",
            min_confidence=0.3,
        )

        assert result is not None
        assert result.project_id == "duckdb"
        # Topic match: 0.6 * (1/1) = 0.6, Domain match: 0.4, Total: 1.0
        assert result.confidence == 1.0

    def test_assign_email_below_threshold(self, temp_db, sample_project):
        """Below confidence threshold returns None."""
        temp_db.execute(
            """INSERT INTO projects (id, name, keywords, sender_domains, email_count, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sample_project.id,
                sample_project.name,
                json.dumps(sample_project.keywords),
                json.dumps(sample_project.sender_domains),
                sample_project.email_count,
                sample_project.first_seen,
                sample_project.last_seen,
            ),
        )
        temp_db.commit()

        result = assign_email(
            conn=temp_db,
            message_id="msg-004",
            topics=["unrelated"],
            sender="user@example.com",
            min_confidence=0.3,
        )

        assert result is None

    def test_assign_email_no_features(self, temp_db, sample_project):
        """No features to match returns None."""
        temp_db.execute(
            """INSERT INTO projects (id, name, keywords, sender_domains, email_count, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                sample_project.id,
                sample_project.name,
                json.dumps(sample_project.keywords),
                json.dumps(sample_project.sender_domains),
                sample_project.email_count,
                sample_project.first_seen,
                sample_project.last_seen,
            ),
        )
        temp_db.commit()

        result = assign_email(
            conn=temp_db,
            message_id="msg-005",
            topics=[],
            sender="",
            min_confidence=0.3,
        )

        assert result is None

    def test_assign_email_multiple_projects(self, temp_db):
        """Returns project with higher score."""

        # Insert two projects
        temp_db.execute(
            """INSERT INTO projects (id, name, keywords, sender_domains, email_count)
               VALUES (?, ?, ?, ?, ?)""",
            ("duckdb", "DuckDB", json.dumps(["duckdb", "database"]), json.dumps([]), 10),
        )
        temp_db.execute(
            """INSERT INTO projects (id, name, keywords, sender_domains, email_count)
               VALUES (?, ?, ?, ?, ?)""",
            ("clickhouse", "ClickHouse", json.dumps(["clickhouse", "database"]), json.dumps([]), 10),
        )
        temp_db.commit()

        # Both match "database", but only duckdb matches "duckdb"
        result = assign_email(
            conn=temp_db,
            message_id="msg-006",
            topics=["duckdb", "clickhouse"],
            sender="user@example.com",
            min_confidence=0.3,
        )

        assert result is not None
        # duckdb: 0.6 * (1/2) = 0.3, clickhouse: 0.6 * (1/2) = 0.3
        # Both same score, should return one of them
        assert result.project_id in ["duckdb", "clickhouse"]

    def test_assign_email_empty_db(self, temp_db):
        """No projects in database returns None."""
        result = assign_email(
            conn=temp_db,
            message_id="msg-007",
            topics=["duckdb"],
            sender="user@example.com",
            min_confidence=0.3,
        )

        assert result is None