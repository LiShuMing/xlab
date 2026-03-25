"""
FastAPI web application for email inbox MVP.

Endpoints:
- GET / : Main inbox page
- GET /settings : Settings page
- GET /api/messages : List messages
- GET /api/messages/{id} : Get message details
- PATCH /api/messages/{id} : Update message state
- POST /api/sync : Trigger sync
- GET /api/settings : Get settings
- PUT /api/settings : Update settings
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from my_email.config import settings
from my_email.db.repository import (
    cleanup_old_messages,
    get_connection,
    get_message_by_id,
    get_message_counts,
    get_messages,
    get_setting,
    init_db,
    save_setting,
    update_message_state,
)
from my_email.scheduler.sync_task import (
    run_sync,
    run_initial_sync,
    start_sync_scheduler,
    start_summarization_worker,
)
from my_email.scheduler.cleanup_task import start_cleanup_scheduler

log = structlog.get_logger()

_TEMPLATE_DIR = Path(__file__).parent / "templates"


# Add custom Jinja2 filter
def from_json(value):
    """Parse JSON string to dict."""
    if not value:
        return {}
    return json.loads(value)


# Create Jinja2 environment
from jinja2 import Environment, FileSystemLoader

jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
jinja_env.filters["from_json"] = from_json


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and start background tasks."""
    import asyncio

    # Initialize database
    init_db()
    log.info("app.startup", db_path=str(settings.db_path))

    # Start background tasks
    sync_task = asyncio.create_task(start_sync_scheduler())
    summary_task = asyncio.create_task(start_summarization_worker())
    cleanup_task = asyncio.create_task(start_cleanup_scheduler())

    # Run initial sync for recent 7 days (non-blocking)
    async def initial_sync_task():
        try:
            await asyncio.sleep(2)  # Wait for server to start
            log.info("app.initial_sync_start", days=7)
            result = await run_initial_sync(days=7)
            log.info("app.initial_sync_complete", **result)
        except Exception as e:
            log.error("app.initial_sync_error", error=str(e))

    asyncio.create_task(initial_sync_task())

    yield

    # Cleanup
    sync_task.cancel()
    summary_task.cancel()
    cleanup_task.cancel()
    log.info("app.shutdown")


app = FastAPI(title="Email Inbox MVP", lifespan=lifespan)


# ── Page Routes ───────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def inbox_page(request: Request):
    """Main inbox page."""
    conn = get_connection()
    try:
        counts = get_message_counts(conn)
        messages = get_messages(conn)
        template = jinja_env.get_template("inbox.html.j2")
        return HTMLResponse(template.render(
            request=request,
            messages=messages,
            counts=counts,
        ))
    finally:
        conn.close()


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Settings page."""
    conn = get_connection()
    try:
        retention_days = int(get_setting(conn, "retention_days", default="7"))
        sync_interval = int(get_setting(conn, "auto_sync_interval_minutes", default="30"))
        template = jinja_env.get_template("settings.html.j2")
        return HTMLResponse(template.render(
            request=request,
            retention_days=retention_days,
            sync_interval=sync_interval,
        ))
    finally:
        conn.close()


# ── API Routes ────────────────────────────────────────────────────────────────


@app.get("/api/messages")
async def list_messages(
    state: str | None = Query(None, description="Filter by state: unread, read, starred, all"),
    relevance: str | None = Query(None, description="Filter by relevance: high, medium, low"),
    days: int | None = Query(None, description="Messages from last N days"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Page size"),
):
    """List messages with optional filters."""
    conn = get_connection()
    try:
        messages = get_messages(conn, state=state, relevance=relevance, days=days, page=page, size=size)
        counts = get_message_counts(conn)

        return {
            "total": counts["total"],
            "unread_count": counts["unread"],
            "high_relevance_count": counts["high_relevance"],
            "messages": [
                {
                    "id": msg["id"],
                    "subject": msg["subject"],
                    "sender": msg["sender"],
                    "sender_email": msg["sender_email"],
                    "received_at": msg["received_at"],
                    "msg_state": msg["msg_state"],
                    "relevance": msg["relevance"],
                    "summary": json.loads(msg["summary_json"]).get("summary") if msg["summary_json"] else None,
                    "thread_count": msg["thread_count"] if msg["thread_count"] and msg["thread_count"] > 1 else None,
                }
                for msg in messages
            ],
        }
    finally:
        conn.close()


@app.get("/api/messages/{message_id}")
async def get_message(message_id: str):
    """Get message details with full body."""
    conn = get_connection()
    try:
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
            "summary": json.loads(msg["summary_json"]) if msg["summary_json"] else None,
        }
    finally:
        conn.close()


@app.patch("/api/messages/{message_id}")
async def patch_message(message_id: str, body: dict[str, str]):
    """Update message state."""
    if "msg_state" not in body:
        raise HTTPException(status_code=400, detail="msg_state is required")

    new_state = body["msg_state"]
    if new_state not in ("read", "starred"):
        raise HTTPException(status_code=400, detail="msg_state must be 'read' or 'starred'")

    conn = get_connection()
    try:
        if not update_message_state(conn, message_id, new_state):
            raise HTTPException(status_code=404, detail="Message not found")
        conn.commit()
        return {"id": message_id, "msg_state": new_state}
    finally:
        conn.close()


@app.post("/api/sync")
async def trigger_sync():
    """Manually trigger sync."""
    try:
        result = await run_sync()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/settings")
async def get_settings():
    """Get current settings."""
    conn = get_connection()
    try:
        return {
            "retention_days": int(get_setting(conn, "retention_days", default="7")),
            "auto_sync_interval_minutes": int(get_setting(conn, "auto_sync_interval_minutes", default="30")),
        }
    finally:
        conn.close()


@app.put("/api/settings")
async def update_settings(body: dict[str, int]):
    """Update settings."""
    conn = get_connection()
    try:
        if "retention_days" in body:
            days = body["retention_days"]
            if not 1 <= days <= 365:
                raise HTTPException(status_code=400, detail="retention_days must be between 1 and 365")
            save_setting(conn, "retention_days", str(days))

        if "auto_sync_interval_minutes" in body:
            interval = body["auto_sync_interval_minutes"]
            if not 5 <= interval <= 1440:
                raise HTTPException(status_code=400, detail="auto_sync_interval_minutes must be between 5 and 1440")
            save_setting(conn, "auto_sync_interval_minutes", str(interval))

        conn.commit()
        return {
            "retention_days": int(get_setting(conn, "retention_days", default="7")),
            "auto_sync_interval_minutes": int(get_setting(conn, "auto_sync_interval_minutes", default="30")),
        }
    finally:
        conn.close()