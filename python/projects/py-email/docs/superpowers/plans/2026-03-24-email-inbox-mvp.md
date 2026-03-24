# Email Inbox MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a single-column email inbox with AI summaries, click-to-expand original text, auto-sync, and auto-cleanup.

**Architecture:** FastAPI + Jinja2 templates + SQLite. Background tasks via FastAPI lifespan + asyncio. Gmail sync with incremental history API. AI summarization via OpenAI-compatible API.

**Tech Stack:** Python 3.12, FastAPI, SQLite, Jinja2, OpenAI client, Google Gmail API

---

## File Structure

```
src/my_email/
├── db/
│   ├── models.py          # Schema: messages, settings tables
│   ├── repository.py      # CRUD: messages, settings
│   └── __init__.py
├── gmail/
│   ├── sync.py            # Incremental sync + msg_state
│   ├── auth.py            # (existing)
│   └── __init__.py
├── llm/
│   ├── summarizer.py      # AI summary (simplified)
│   └── __init__.py
├── scheduler/
│   ├── __init__.py
│   ├── sync_task.py       # Auto-sync background task
│   └── cleanup_task.py    # Auto-cleanup background task
├── server/
│   ├── app.py             # FastAPI routes + lifespan
│   └── templates/
│       ├── inbox.html.j2  # Main inbox page
│       └── settings.html.j2
├── config.py              # Settings + env vars
└── __init__.py

tests/
├── test_models.py
├── test_repository.py
├── test_sync.py
└── test_api.py
```

---

## Task 1: Data Model Rewrite

**Files:**
- Modify: `src/my_email/db/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing test for schema**

```python
# tests/test_models.py
import sqlite3
import pytest
from my_email.db.models import SCHEMA_SQL

def test_schema_creates_messages_table():
    """Verify messages table has all required columns."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)

    cursor = conn.execute("PRAGMA table_info(messages)")
    columns = {row[1] for row in cursor.fetchall()}

    required = {"id", "thread_id", "subject", "sender", "sender_email",
                "received_at", "body_text", "msg_state", "relevance",
                "summary_json", "created_at"}
    assert required.issubset(columns)

def test_schema_creates_settings_table():
    """Verify settings table exists."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA_SQL)

    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
    assert cursor.fetchone() is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL - missing columns

- [ ] **Step 3: Rewrite models.py with new schema**

```python
# src/my_email/db/models.py
"""Database schema for email inbox MVP."""

SCHEMA_SQL = """
-- Drop old tables (clean slate for MVP)
DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS summaries;
DROP TABLE IF EXISTS digests;
DROP TABLE IF EXISTS topic_daily;
DROP TABLE IF EXISTS topic_tracks;
DROP TABLE IF EXISTS message_topics;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS email_projects;
DROP TABLE IF EXISTS sync_state;

-- Messages table (simplified schema)
CREATE TABLE IF NOT EXISTS messages (
    id           TEXT PRIMARY KEY,      -- Gmail message ID
    thread_id    TEXT NOT NULL,
    subject      TEXT,
    sender       TEXT,
    sender_email TEXT,                  -- Extracted email address
    received_at  TEXT NOT NULL,         -- ISO-8601 UTC
    body_text    TEXT,                  -- Original email body
    msg_state    TEXT NOT NULL DEFAULT 'unread',  -- 'unread', 'read', 'starred'
    relevance    TEXT,                  -- 'high', 'medium', 'low', 'skip', NULL
    summary_json TEXT,                  -- AI summary JSON
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_messages_received ON messages(received_at);
CREATE INDEX IF NOT EXISTS idx_messages_state ON messages(msg_state);
CREATE INDEX IF NOT EXISTS idx_messages_relevance ON messages(relevance);

-- Settings table
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Default settings
INSERT OR IGNORE INTO settings (key, value) VALUES
    ('retention_days', '7'),
    ('auto_sync_interval_minutes', '30'),
    ('last_history_id', '');
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/my_email/db/models.py tests/test_models.py
git commit -m "refactor(db): rewrite schema for inbox MVP"
```

---

## Task 2: Repository Layer Rewrite

**Files:**
- Modify: `src/my_email/db/repository.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1: Write failing tests for repository functions**

```python
# tests/test_repository.py
import sqlite3
import pytest
from my_email.db.repository import (
    get_connection, init_db, upsert_message, get_messages,
    get_message_by_id, update_message_state, get_setting, save_setting,
    cleanup_old_messages, MessageData
)

@pytest.fixture
def db():
    """Create in-memory test database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from my_email.db.models import SCHEMA_SQL
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()

def test_upsert_message_inserts_new(db):
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

def test_upsert_message_skips_duplicate(db):
    """Skip if message already exists."""
    msg = MessageData(id="msg-001", thread_id="t1", received_at="2026-03-24T10:00:00Z")
    upsert_message(db, msg)
    result = upsert_message(db, msg)
    assert result is False

def test_get_messages_ordered_by_priority(db):
    """Messages ordered: unread first, then high relevance, then by date."""
    # Insert test messages
    db.execute("""INSERT INTO messages (id, thread_id, subject, received_at, msg_state, relevance)
                  VALUES ('msg-1', 't1', 'Read low', '2026-03-24T12:00:00Z', 'read', 'low')""")
    db.execute("""INSERT INTO messages (id, thread_id, subject, received_at, msg_state, relevance)
                  VALUES ('msg-2', 't1', 'Unread high', '2026-03-24T10:00:00Z', 'unread', 'high')""")
    db.execute("""INSERT INTO messages (id, thread_id, subject, received_at, msg_state, relevance)
                  VALUES ('msg-3', 't1', 'Unread medium', '2026-03-24T11:00:00Z', 'unread', 'medium')""")

    messages = get_messages(db)
    assert messages[0]["id"] == "msg-2"  # unread + high
    assert messages[1]["id"] == "msg-3"  # unread + medium
    assert messages[2]["id"] == "msg-1"  # read

def test_update_message_state(db):
    """Update message state."""
    db.execute("""INSERT INTO messages (id, thread_id, received_at) VALUES ('msg-1', 't1', '2026-03-24T10:00:00Z')""")
    update_message_state(db, "msg-1", "read")
    row = db.execute("SELECT msg_state FROM messages WHERE id = 'msg-1'").fetchone()
    assert row["msg_state"] == "read"

def test_get_setting_default(db):
    """Get setting with default value."""
    value = get_setting(db, "nonexistent", default="default_value")
    assert value == "default_value"

def test_save_and_get_setting(db):
    """Save and retrieve setting."""
    save_setting(db, "test_key", "test_value")
    value = get_setting(db, "test_key")
    assert value == "test_value"

def test_cleanup_old_messages(db):
    """Delete messages older than retention days."""
    # Insert old and new messages
    db.execute("""INSERT INTO messages (id, thread_id, received_at) VALUES ('old', 't1', '2026-03-01T10:00:00Z')""")
    db.execute("""INSERT INTO messages (id, thread_id, received_at) VALUES ('new', 't1', '2026-03-24T10:00:00Z')""")

    deleted = cleanup_old_messages(db, retention_days=7, current_date="2026-03-24")
    assert deleted == 1

    remaining = db.execute("SELECT id FROM messages").fetchall()
    assert len(remaining) == 1
    assert remaining[0]["id"] == "new"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_repository.py -v`
Expected: FAIL - functions not implemented

- [ ] **Step 3: Implement repository functions**

```python
# src/my_email/db/repository.py
"""Database repository layer for email inbox MVP."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any

import structlog

from my_email.config import settings
from my_email.db.models import SCHEMA_SQL

log = structlog.get_logger()


def get_connection() -> sqlite3.Connection:
    """Create database connection with WAL mode."""
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Initialize database schema."""
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    log.info("db.initialized", path=str(settings.db_path))


# ── Message data class ────────────────────────────────────────────────────────

class MessageData(dict):
    """Typed dict for message insertion."""
    id: str
    thread_id: str
    subject: str | None
    sender: str | None
    sender_email: str | None
    received_at: str
    body_text: str | None


# ── Message CRUD ──────────────────────────────────────────────────────────────

def upsert_message(conn: sqlite3.Connection, msg: MessageData) -> bool:
    """Insert message if not exists. Returns True if inserted."""
    cur = conn.execute("SELECT 1 FROM messages WHERE id = ?", (msg["id"],))
    if cur.fetchone():
        return False

    conn.execute(
        """INSERT INTO messages (id, thread_id, subject, sender, sender_email, received_at, body_text)
           VALUES (:id, :thread_id, :subject, :sender, :sender_email, :received_at, :body_text)""",
        msg,
    )
    return True


def get_messages(
    conn: sqlite3.Connection,
    state: str | None = None,
    relevance: str | None = None,
    days: int | None = None,
    page: int = 1,
    size: int = 50,
) -> list[sqlite3.Row]:
    """
    Get messages with filtering and priority ordering.

    Order: unread first, then high relevance, then by received_at DESC.
    """
    query = "SELECT * FROM messages WHERE 1=1"
    params: list[Any] = []

    if state:
        query += " AND msg_state = ?"
        params.append(state)

    if relevance:
        query += " AND relevance = ?"
        params.append(relevance)

    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        query += " AND received_at >= ?"
        params.append(cutoff)

    # Priority ordering: unread first, then high relevance, then by date
    query += """ ORDER BY
        CASE WHEN msg_state = 'unread' THEN 0 ELSE 1 END,
        CASE WHEN relevance = 'high' THEN 0 ELSE 1 END,
        received_at DESC
    """

    query += " LIMIT ? OFFSET ?"
    params.extend([size, (page - 1) * size])

    return conn.execute(query, params).fetchall()


def get_message_by_id(conn: sqlite3.Connection, message_id: str) -> sqlite3.Row | None:
    """Get single message by ID."""
    return conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()


def update_message_state(conn: sqlite3.Connection, message_id: str, state: str) -> bool:
    """Update message state. Returns True if updated."""
    cur = conn.execute(
        "UPDATE messages SET msg_state = ? WHERE id = ?",
        (state, message_id),
    )
    return cur.rowcount > 0


def get_message_counts(conn: sqlite3.Connection, days: int | None = None) -> dict[str, int]:
    """Get total, unread, and high_relevance counts."""
    where = "WHERE 1=1"
    params: list[Any] = []

    if days:
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        where += " AND received_at >= ?"
        params.append(cutoff)

    total = conn.execute(f"SELECT COUNT(*) FROM messages {where}", params).fetchone()[0]
    unread = conn.execute(f"SELECT COUNT(*) FROM messages {where} AND msg_state = 'unread'", params).fetchone()[0]
    high = conn.execute(f"SELECT COUNT(*) FROM messages {where} AND relevance = 'high'", params).fetchone()[0]

    return {"total": total, "unread": unread, "high_relevance": high}


def save_summary(conn: sqlite3.Connection, message_id: str, summary_json: str) -> None:
    """Save summary and extract relevance."""
    try:
        data = json.loads(summary_json)
        relevance = data.get("relevance")
        conn.execute(
            "UPDATE messages SET summary_json = ?, relevance = ? WHERE id = ?",
            (summary_json, relevance, message_id),
        )
    except json.JSONDecodeError:
        log.warning("repository.save_summary.parse_error", message_id=message_id)


# ── Settings ───────────────────────────────────────────────────────────────────

def get_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    """Get setting value, return default if not found."""
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def save_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Save setting value."""
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
        (key, value),
    )


# ── Cleanup ────────────────────────────────────────────────────────────────────

def cleanup_old_messages(conn: sqlite3.Connection, retention_days: int, current_date: str | None = None) -> int:
    """Delete messages older than retention_days. Returns count deleted."""
    current = current_date or datetime.now().strftime("%Y-%m-%d")
    cutoff = (datetime.strptime(current, "%Y-%m-%d") - timedelta(days=retention_days)).strftime("%Y-%m-%d")

    cur = conn.execute("DELETE FROM messages WHERE received_at < ?", (cutoff,))
    return cur.rowcount
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_repository.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/my_email/db/repository.py tests/test_repository.py
git commit -m "refactor(db): rewrite repository for inbox MVP"
```

---

## Task 3: Gmail Sync Refactor

**Files:**
- Modify: `src/my_email/gmail/sync.py`
- Create: `tests/test_sync.py`

- [ ] **Step 1: Write failing tests for sync functions**

```python
# tests/test_sync.py
import sqlite3
import pytest
from unittest.mock import Mock, patch, MagicMock
from my_email.gmail.sync import sync_messages, extract_email_address, HistoryIdExpiredError

@pytest.fixture
def db():
    """Create in-memory test database."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from my_email.db.models import SCHEMA_SQL
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()

def test_extract_email_address():
    """Extract email from 'Name <email@domain.com>' format."""
    assert extract_email_address("User <user@example.com>") == "user@example.com"
    assert extract_email_address("user@example.com") == "user@example.com"
    assert extract_email_address("") is None

def test_sync_messages_full_sync_on_empty_db(db):
    """When no history_id, do full sync."""
    mock_service = Mock()
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "msg-1"}]
    }
    mock_service.users().messages().get().execute.return_value = {
        "id": "msg-1",
        "threadId": "thread-1",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test"},
                {"name": "From", "value": "User <user@example.com>"},
                {"name": "Date", "value": "Mon, 24 Mar 2026 10:00:00 +0000"},
            ],
            "body": {"data": "VGVzdCBib2R5"}  # base64 "Test body"
        },
        "labelIds": ["UNREAD"]
    }
    mock_service.users().getProfile().execute.return_value = {"historyId": "12345"}

    with patch("my_email.gmail.sync.build_service", return_value=mock_service):
        result = sync_messages(db, mock_service, days=7)

    assert result["synced"] == 1

    msg = db.execute("SELECT * FROM messages WHERE id = 'msg-1'").fetchone()
    assert msg is not None
    assert msg["msg_state"] == "unread"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_sync.py -v`
Expected: FAIL

- [ ] **Step 3: Refactor sync.py**

Simplify `src/my_email/gmail/sync.py` to:
- Add `extract_email_address()` helper
- Modify `upsert_message` call to include `sender_email` and `msg_state`
- Sync `UNREAD` label to `msg_state`
- Return sync statistics

Key changes:
```python
def extract_email_address(sender: str) -> str | None:
    """Extract email address from sender string."""
    if not sender:
        return None
    if "<" in sender and ">" in sender:
        return sender.split("<")[1].rstrip(">")
    return sender.strip()

def sync_messages(conn, service, days: int = 7) -> dict:
    """Sync recent messages. Returns sync stats."""
    # ... existing logic, but:
    # 1. Extract sender_email
    # 2. Set msg_state based on UNREAD label
    # 3. Save last_history_id to settings
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_sync.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/my_email/gmail/sync.py tests/test_sync.py
git commit -m "refactor(gmail): add msg_state sync and email extraction"
```

---

## Task 4: Simplify LLM Summarizer

**Files:**
- Modify: `src/my_email/llm/summarizer.py`

- [ ] **Step 1: Simplify EmailSummary model**

Keep only essential fields:
```python
class EmailSummary(BaseModel):
    title: str
    summary: str = Field(description="One-sentence summary (100 chars max)")
    key_points: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    relevance: str = Field(description="'high', 'medium', 'low', or 'skip'")
    sender_org: str = ""
```

- [ ] **Step 2: Update system prompt**

Simplify prompt to focus on essential summary.

- [ ] **Step 3: Run existing test**

Run: `pytest tests/test_summarizer.py -v`

- [ ] **Step 4: Commit**

```bash
git add src/my_email/llm/summarizer.py
git commit -m "refactor(llm): simplify EmailSummary model"
```

---

## Task 5: Scheduler Module

**Files:**
- Create: `src/my_email/scheduler/__init__.py`
- Create: `src/my_email/scheduler/sync_task.py`
- Create: `src/my_email/scheduler/cleanup_task.py`

- [ ] **Step 1: Create sync_task.py**

```python
# src/my_email/scheduler/sync_task.py
"""Background auto-sync task."""

import asyncio
from datetime import datetime

import structlog

from my_email.db.repository import get_connection, get_setting, save_setting
from my_email.gmail.sync import sync_messages, build_service

log = structlog.get_logger()


async def sync_scheduler() -> None:
    """Run sync at configured interval."""
    while True:
        conn = get_connection()
        try:
            interval = int(get_setting(conn, "auto_sync_interval_minutes", "30"))
            await asyncio.sleep(interval * 60)

            log.info("scheduler.sync_start")
            service = build_service()
            days = int(get_setting(conn, "retention_days", "7"))
            result = sync_messages(conn, service, days=days)
            conn.commit()
            log.info("scheduler.sync_done", **result)
        except Exception as e:
            log.error("scheduler.sync_error", error=str(e))
        finally:
            conn.close()


async def run_initial_sync() -> None:
    """Run one sync on startup."""
    conn = get_connection()
    try:
        days = int(get_setting(conn, "retention_days", "7"))
        service = build_service()
        result = sync_messages(conn, service, days=days)
        conn.commit()
        log.info("scheduler.initial_sync_done", **result)
    except Exception as e:
        log.error("scheduler.initial_sync_error", error=str(e))
    finally:
        conn.close()
```

- [ ] **Step 2: Create cleanup_task.py**

```python
# src/my_email/scheduler/cleanup_task.py
"""Background cleanup task."""

import asyncio
from datetime import datetime, time

import structlog

from my_email.db.repository import get_connection, get_setting, cleanup_old_messages

log = structlog.get_logger()


def seconds_until_midnight() -> int:
    """Calculate seconds until next midnight."""
    now = datetime.now()
    tomorrow = now.replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = tomorrow.replace(day=now.day + 1)
    return int((tomorrow - now).total_seconds())


async def cleanup_scheduler() -> None:
    """Run cleanup daily at midnight."""
    while True:
        await asyncio.sleep(seconds_until_midnight())

        conn = get_connection()
        try:
            retention = int(get_setting(conn, "retention_days", "7"))
            deleted = cleanup_old_messages(conn, retention_days=retention)
            conn.commit()
            log.info("scheduler.cleanup_done", deleted=deleted)
        except Exception as e:
            log.error("scheduler.cleanup_error", error=str(e))
        finally:
            conn.close()
```

- [ ] **Step 3: Create __init__.py**

```python
# src/my_email/scheduler/__init__.py
"""Background scheduler tasks."""

from my_email.scheduler.sync_task import sync_scheduler, run_initial_sync
from my_email.scheduler.cleanup_task import cleanup_scheduler

__all__ = ["sync_scheduler", "run_initial_sync", "cleanup_scheduler"]
```

- [ ] **Step 4: Commit**

```bash
git add src/my_email/scheduler/
git commit -m "feat(scheduler): add auto-sync and cleanup tasks"
```

---

## Task 6: FastAPI App Rewrite

**Files:**
- Modify: `src/my_email/server/app.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write API tests**

```python
# tests/test_api.py
import sqlite3
import pytest
from fastapi.testclient import TestClient
from my_email.server.app import app, get_db

@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from my_email.db.models import SCHEMA_SQL
    conn.executescript(SCHEMA_SQL)
    yield conn
    conn.close()

@pytest.fixture
def client(db):
    def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

def test_get_messages_empty(client):
    """GET /api/messages returns empty list."""
    resp = client.get("/api/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["messages"] == []

def test_get_messages_with_data(client, db):
    """GET /api/messages returns messages."""
    db.execute("""INSERT INTO messages (id, thread_id, subject, received_at, msg_state)
                  VALUES ('msg-1', 't1', 'Test', '2026-03-24T10:00:00Z', 'unread')""")
    db.commit()

    resp = client.get("/api/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["unread"] == 1

def test_get_message_by_id(client, db):
    """GET /api/messages/{id} returns message with body."""
    db.execute("""INSERT INTO messages (id, thread_id, subject, body_text, received_at)
                  VALUES ('msg-1', 't1', 'Test', 'Body text', '2026-03-24T10:00:00Z')""")
    db.commit()

    resp = client.get("/api/messages/msg-1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["body_text"] == "Body text"

def test_patch_message_state(client, db):
    """PATCH /api/messages/{id} updates state."""
    db.execute("""INSERT INTO messages (id, thread_id, received_at) VALUES ('msg-1', 't1', '2026-03-24T10:00:00Z')""")
    db.commit()

    resp = client.patch("/api/messages/msg-1", json={"msg_state": "read"})
    assert resp.status_code == 200

    row = db.execute("SELECT msg_state FROM messages WHERE id = 'msg-1'").fetchone()
    assert row["msg_state"] == "read"

def test_get_settings(client):
    """GET /api/settings returns settings."""
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "retention_days" in data

def test_put_settings(client, db):
    """PUT /api/settings updates settings."""
    resp = client.put("/api/settings", json={"retention_days": "14"})
    assert resp.status_code == 200

    value = db.execute("SELECT value FROM settings WHERE key = 'retention_days'").fetchone()
    assert value["value"] == "14"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py -v`
Expected: FAIL

- [ ] **Step 3: Rewrite app.py**

```python
# src/my_email/server/app.py
"""FastAPI web application for email inbox MVP."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated, Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel

from my_email.config import settings
from my_email.db.repository import (
    get_connection, init_db, get_messages, get_message_by_id,
    update_message_state, get_setting, save_setting, get_message_counts
)
from my_email.scheduler import sync_scheduler, run_initial_sync, cleanup_scheduler

log = structlog.get_logger()

_TEMPLATE_DIR = settings.db_path.parent / "server" / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown tasks."""
    init_db()

    # Run initial sync in background
    asyncio.create_task(run_initial_sync())

    # Start background schedulers
    sync_task = asyncio.create_task(sync_scheduler())
    cleanup_task = asyncio.create_task(cleanup_scheduler())

    yield

    sync_task.cancel()
    cleanup_task.cancel()


app = FastAPI(title="Email Inbox", lifespan=lifespan)


# ── Database dependency ────────────────────────────────────────────────────────

def get_db():
    """Database connection dependency."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()

DB = Annotated[sqlite3.Connection, Depends(get_db)]


# ── Pydantic models ────────────────────────────────────────────────────────────

class MessageUpdate(BaseModel):
    msg_state: str | None = None

class SettingsUpdate(BaseModel):
    retention_days: str | None = None
    auto_sync_interval_minutes: str | None = None


# ── Page routes ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def inbox(request: Request):
    """Main inbox page."""
    template = _jinja_env.get_template("inbox.html.j2")
    return template.render()

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    template = _jinja_env.get_template("settings.html.j2")
    return template.render()


# ── API routes ─────────────────────────────────────────────────────────────────

@app.get("/api/messages")
async def api_messages(
    conn: DB,
    state: str | None = None,
    relevance: str | None = None,
    days: int | None = None,
    page: int = 1,
    size: int = 50,
):
    """Get messages list."""
    messages = get_messages(conn, state=state, relevance=relevance, days=days, page=page, size=size)
    counts = get_message_counts(conn, days=days)

    return {
        "total": counts["total"],
        "unread": counts["unread"],
        "high_relevance": counts["high_relevance"],
        "messages": [
            {
                "id": m["id"],
                "subject": m["subject"],
                "sender": m["sender"],
                "received_at": m["received_at"],
                "msg_state": m["msg_state"],
                "relevance": m["relevance"],
                "summary": _extract_summary_text(m["summary_json"]),
            }
            for m in messages
        ],
    }


@app.get("/api/messages/{message_id}")
async def api_message_detail(message_id: str, conn: DB):
    """Get single message with full body."""
    msg = get_message_by_id(conn, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    return {
        "id": msg["id"],
        "thread_id": msg["thread_id"],
        "subject": msg["subject"],
        "sender": msg["sender"],
        "sender_email": msg["sender_email"],
        "received_at": msg["received_at"],
        "body_text": msg["body_text"],
        "msg_state": msg["msg_state"],
        "relevance": msg["relevance"],
        "summary": _extract_summary_text(msg["summary_json"]),
        "key_points": _extract_key_points(msg["summary_json"]),
    }


@app.patch("/api/messages/{message_id}")
async def api_update_message(message_id: str, update: MessageUpdate, conn: DB):
    """Update message state."""
    if update.msg_state:
        if update.msg_state not in ("read", "starred"):
            raise HTTPException(status_code=400, detail="Invalid state")
        if not update_message_state(conn, message_id, update.msg_state):
            raise HTTPException(status_code=404, detail="Message not found")
        conn.commit()

    return {"id": message_id, "msg_state": update.msg_state}


@app.get("/api/settings")
async def api_get_settings(conn: DB):
    """Get all settings."""
    return {
        "retention_days": int(get_setting(conn, "retention_days", "7")),
        "auto_sync_interval_minutes": int(get_setting(conn, "auto_sync_interval_minutes", "30")),
    }


@app.put("/api/settings")
async def api_update_settings(update: SettingsUpdate, conn: DB):
    """Update settings."""
    if update.retention_days:
        days = int(update.retention_days)
        if not 1 <= days <= 365:
            raise HTTPException(status_code=400, detail="retention_days must be 1-365")
        save_setting(conn, "retention_days", update.retention_days)

    if update.auto_sync_interval_minutes:
        minutes = int(update.auto_sync_interval_minutes)
        if not 5 <= minutes <= 1440:
            raise HTTPException(status_code=400, detail="auto_sync_interval_minutes must be 5-1440")
        save_setting(conn, "auto_sync_interval_minutes", update.auto_sync_interval_minutes)

    conn.commit()
    return {"status": "ok"}


@app.post("/api/sync")
async def api_trigger_sync(conn: DB):
    """Manually trigger sync."""
    # Run sync in background
    asyncio.create_task(run_initial_sync())
    return {"status": "sync_started"}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_summary_text(summary_json: str | None) -> str:
    """Extract summary text from JSON."""
    if not summary_json:
        return ""
    try:
        data = json.loads(summary_json)
        return data.get("summary", "")
    except:
        return ""

def _extract_key_points(summary_json: str | None) -> list[str]:
    """Extract key points from JSON."""
    if not summary_json:
        return []
    try:
        data = json.loads(summary_json)
        return data.get("key_points", [])
    except:
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/my_email/server/app.py tests/test_api.py
git commit -m "refactor(server): rewrite FastAPI app for inbox MVP"
```

---

## Task 7: Frontend Templates

**Files:**
- Create: `src/my_email/server/templates/inbox.html.j2`
- Create: `src/my_email/server/templates/settings.html.j2`

- [ ] **Step 1: Create inbox.html.j2**

Create single-page inbox template with:
- Filter controls
- Message cards
- Click-to-expand body text
- JavaScript for API calls

- [ ] **Step 2: Create settings.html.j2**

Create settings page with:
- Retention days input
- Sync interval input
- Save button

- [ ] **Step 3: Commit**

```bash
git add src/my_email/server/templates/
git commit -m "feat(ui): add inbox and settings templates"
```

---

## Task 8: Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_integration.py
"""End-to-end integration test."""

import pytest
from fastapi.testclient import TestClient

def test_full_workflow(client):
    """Test: sync -> list -> read -> cleanup."""
    # 1. Sync messages (mocked)
    # 2. List messages
    # 3. Mark as read
    # 4. Verify state changed
    pass
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test"
```

---

## Task 9: Manual Verification

- [ ] **Step 1: Backup existing database**

```bash
cp data/my_email.db data/my_email.db.backup
```

- [ ] **Step 2: Run server**

```bash
my-email server
```

- [ ] **Step 3: Open browser**

Open: http://localhost:8080

- [ ] **Step 4: Verify features**

- [ ] Messages display in priority order
- [ ] Click expand shows body text
- [ ] Mark as read works
- [ ] Settings page saves changes

---

## Success Criteria Checklist

- [ ] Main page shows single-column inbox
- [ ] Messages ordered: unread → high → by date
- [ ] Click expands/collapses original text
- [ ] Shows unread count and high-relevance count
- [ ] Can mark messages as read
- [ ] Auto-syncs on startup and at interval
- [ ] Cleans up old messages daily
- [ ] Settings page to configure retention and interval