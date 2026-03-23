"""
FastAPI web application for browsing email digests.

Endpoints:
- GET / : Main page with date list and digest viewer
- GET /api/dates : List all available digest dates
- GET /api/digest/{date} : Get HTML digest for a date
- POST /api/generate/{date} : Trigger sync+summarize for a date
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import date as Date, timedelta
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from my_email.config import settings
from my_email.db.repository import get_connection, init_db, get_digest

log = structlog.get_logger()

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# Background task status tracking
_task_status: dict[str, dict[str, Any]] = {}

# Thread pool for background processing
_executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="email-worker")


def _get_all_digest_dates(conn: sqlite3.Connection) -> list[str]:
    """
    Fetch all dates that have a stored digest.

    Args:
        conn: Database connection.

    Returns:
        List of date strings in YYYY-MM-DD format, most recent first.
    """
    rows = conn.execute(
        "SELECT date FROM digests ORDER BY date DESC"
    ).fetchall()
    return [row["date"] for row in rows]


def _get_messages_count_for_date(conn: sqlite3.Connection, target_date: str) -> int:
    """
    Count messages for a specific date.

    Args:
        conn: Database connection.
        target_date: YYYY-MM-DD date string.

    Returns:
        Number of messages received on that date.
    """
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE received_at LIKE ?",
        (f"{target_date}%",),
    ).fetchone()
    return row["cnt"] if row else 0


def _get_processed_count_for_date(conn: sqlite3.Connection, target_date: str) -> int:
    """
    Count processed messages for a specific date.

    Args:
        conn: Database connection.
        target_date: YYYY-MM-DD date string.

    Returns:
        Number of processed messages for that date.
    """
    row = conn.execute(
        """SELECT COUNT(*) as cnt FROM messages
           WHERE received_at LIKE ? AND processed = 1""",
        (f"{target_date}%",),
    ).fetchone()
    return row["cnt"] if row else 0


def _run_sync_summarize_sync(target_date: str) -> dict[str, Any]:
    """
    Synchronous version: Run sync and summarize for a specific date.

    This runs in a thread pool worker.

    Args:
        target_date: YYYY-MM-DD date string.

    Returns:
        Dict with status and counts.
    """
    from my_email.gmail.sync import incremental_sync
    from my_email.db.repository import get_sync_state, save_summary, save_thread_summary, get_connection
    from my_email.llm import (
        EmailFilter,
        ThreadAggregator,
        summarize_message,
        summarize_thread,
        LLMSummarizationError,
    )

    result: dict[str, Any] = {
        "date": target_date,
        "sync_count": 0,
        "summarize_ok": 0,
        "summarize_fail": 0,
        "error": None,
    }

    try:
        conn = get_connection()

        # Step 1: Run incremental sync
        state = get_sync_state(conn)
        if state:
            sync_count, _ = incremental_sync(conn)
            result["sync_count"] = sync_count
            log.info("server.background_sync_done", date=target_date, count=sync_count)

        # Step 2: Get unprocessed messages for the date
        rows = conn.execute(
            "SELECT * FROM messages WHERE processed = 0 AND received_at LIKE ? ORDER BY received_at",
            (f"{target_date}%",),
        ).fetchall()
        messages = [dict(row) for row in rows]

        if not messages:
            log.info("server.no_messages_to_summarize", date=target_date)
            conn.close()
            return result

        # Step 3: Filter and aggregate
        email_filter = EmailFilter(
            exclude_starrocks=True,
            exclude_auto_reply=True,
            exclude_noreply=False,
        )
        messages, _ = email_filter.filter_messages(messages)

        if messages:
            aggregator = ThreadAggregator(
                use_thread_id=True,
                use_subject_similarity=True,
                min_group_size=1,
            )
            aggregated = aggregator.aggregate(messages)

            # Step 4: Summarize
            for group in aggregated:
                try:
                    if group.get("is_thread"):
                        summary = summarize_thread(
                            subject=group["base_subject"],
                            message_count=group["message_count"],
                            date_range=group["date_range"],
                            combined_body=group["combined_body"],
                        )
                        save_thread_summary(
                            conn,
                            group["message_ids"],
                            summary.model_dump_json(),
                            settings.llm_model,
                        )
                    else:
                        msg = group["messages"][0]
                        summary = summarize_message(
                            subject=msg.get("subject", "") or "",
                            sender=msg.get("sender", "") or "",
                            date=msg.get("received_at", ""),
                            body=msg.get("body_text", "") or "",
                        )
                        save_summary(conn, msg["id"], summary.model_dump_json(), settings.llm_model)

                    conn.commit()
                    result["summarize_ok"] += 1
                except LLMSummarizationError as e:
                    result["summarize_fail"] += 1
                    log.error("server.summarize_error", error=str(e))

        conn.close()
        log.info("server.background_task_done", **result)

    except Exception as e:
        result["error"] = str(e)
        log.error("server.background_task_failed", date=target_date, error=str(e))

    return result


def _build_digest_for_date_sync(target_date: str) -> bool:
    """
    Synchronous version: Build digest for a date after summarization.

    Args:
        target_date: YYYY-MM-DD date string.

    Returns:
        True if digest was built successfully.
    """
    from my_email.digest.builder import build_digest
    from my_email.db.repository import save_digest, get_connection
    from my_email.db.topic_repository import upsert_topic_tracks

    try:
        conn = get_connection()
        result = build_digest(conn, target_date)

        if result.total_emails == 0:
            conn.close()
            return False

        save_digest(conn, target_date, result.model_dump_json())
        upsert_topic_tracks(conn, target_date, result.topic_clusters)
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log.error("server.build_digest_error", date=target_date, error=str(e))
        return False


def _process_single_date(target_date: str) -> None:
    """
    Process a single date: sync + summarize + digest.
    Runs in thread pool.
    """
    from my_email.db.repository import get_connection, get_digest

    # Check if already has digest
    conn = get_connection()
    digest_row = get_digest(conn, date=target_date)
    processed = conn.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE received_at LIKE ? AND processed = 1",
        (f"{target_date}%",),
    ).fetchone()
    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM messages WHERE received_at LIKE ?",
        (f"{target_date}%",),
    ).fetchone()
    conn.close()

    # Skip if already has digest
    if digest_row:
        log.info("server.auto_process_skip", date=target_date, reason="has_digest")
        _task_status[target_date] = {"status": "completed", "reason": "already_has_digest"}
        return

    # Skip if no messages
    if total["cnt"] == 0:
        log.info("server.auto_process_skip", date=target_date, reason="no_messages")
        _task_status[target_date] = {"status": "skipped", "reason": "no_messages"}
        return

    # Skip if all already processed but no digest (will build digest)
    if processed["cnt"] > 0 and processed["cnt"] == total["cnt"]:
        log.info("server.auto_process_building_digest", date=target_date)
        _task_status[target_date] = {"status": "running", "step": "building_digest"}
        ok = _build_digest_for_date_sync(target_date)
        if ok:
            _task_status[target_date] = {"status": "completed"}
        else:
            _task_status[target_date] = {"status": "no_data"}
        return

    # Need to run full pipeline
    log.info("server.auto_process_running", date=target_date, messages=total["cnt"], processed=processed["cnt"])
    _task_status[target_date] = {"status": "running", "step": "sync"}

    result = _run_sync_summarize_sync(target_date)
    _task_status[target_date]["sync_result"] = result

    if result.get("error"):
        _task_status[target_date]["status"] = "failed"
        _task_status[target_date]["error"] = result["error"]
        return

    ok = _build_digest_for_date_sync(target_date)
    if ok:
        _task_status[target_date]["status"] = "completed"
    else:
        _task_status[target_date]["status"] = "no_data"


def _process_multiple_dates(dates: list[str]) -> None:
    """
    Process multiple dates in parallel using thread pool.
    """
    log.info("server.parallel_process_start", dates=dates, workers=_executor._max_workers)

    futures = []
    for date_str in dates:
        if _task_status.get(date_str, {}).get("status") == "running":
            continue
        _task_status[date_str] = {"status": "pending"}
        future = _executor.submit(_process_single_date, date_str)
        futures.append((date_str, future))

    # Wait for all to complete (non-blocking for web server)
    for date_str, future in futures:
        try:
            future.result(timeout=600)  # 10 min timeout per date
        except Exception as e:
            log.error("server.parallel_process_error", date=date_str, error=str(e))
            _task_status[date_str] = {"status": "failed", "error": str(e)}

    log.info("server.parallel_process_done")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database and auto-process last 7 days on startup."""
    init_db()

    # Schedule background processing (non-blocking)
    async def schedule_processing() -> None:
        await asyncio.sleep(1)  # Wait for server to be ready

        dates_to_process = []
        for i in range(7):
            d = Date.today() - timedelta(days=i)
            date_str = d.strftime("%Y-%m-%d")
            dates_to_process.append(date_str)

        # Run in thread pool (non-blocking for asyncio)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(_executor, _process_multiple_dates, dates_to_process)

    asyncio.create_task(schedule_processing())
    yield

    # Cleanup on shutdown
    _executor.shutdown(wait=False)


app = FastAPI(
    title="my-email digest viewer",
    description="Web interface for browsing daily email digests",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Main page showing all digest dates with viewer.
    Defaults to showing last 7 days.
    """
    try:
        from jinja2 import Environment, FileSystemLoader
    except ImportError:
        raise HTTPException(status_code=500, detail="jinja2 not installed")

    conn = get_connection()
    dates = _get_all_digest_dates(conn)
    conn.close()

    today = Date.today().strftime("%Y-%m-%d")

    # Generate date list for the past 7 days (changed from 30)
    available_dates: list[dict[str, Any]] = []
    for i in range(7):
        d = Date.today() - timedelta(days=i)
        date_str = d.strftime("%Y-%m-%d")

        conn = get_connection()
        has_digest = date_str in dates
        msg_count = _get_messages_count_for_date(conn, date_str)
        processed_count = _get_processed_count_for_date(conn, date_str)
        conn.close()

        task_info = _task_status.get(date_str, {})

        available_dates.append({
            "date": date_str,
            "has_digest": has_digest,
            "msg_count": msg_count,
            "processed_count": processed_count,
            "is_today": date_str == today,
            "task_status": task_info.get("status") if task_info else None,
        })

    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)), autoescape=True)
    template = env.get_template("index.html.j2")
    html = template.render(
        dates=available_dates,
        today=today,
    )

    return HTMLResponse(content=html)


@app.get("/api/dates")
async def list_dates():
    """
    List all dates with digests.
    """
    conn = get_connection()
    dates = _get_all_digest_dates(conn)
    conn.close()
    return {"dates": dates}


@app.get("/api/digest/{target_date}", response_class=HTMLResponse)
async def get_digest_html(target_date: str):
    """
    Get HTML digest for a specific date.

    If no digest exists but there are messages, triggers generation.
    """
    from my_email.digest.builder import build_digest
    from my_email.db.topic_repository import get_active_topics
    from my_email.digest.renderer import build_html_digest, TemplateError

    conn = get_connection()

    # Check for existing digest
    digest_row = get_digest(conn, target_date)

    if digest_row:
        # Digest exists - build HTML from stored data
        from my_email.digest.builder import DailyDigest

        digest_data = json.loads(digest_row["digest_json"])
        digest = DailyDigest(**digest_data)
        active_topics = get_active_topics(conn, target_date)
        conn.close()

        try:
            html = build_html_digest(digest, active_topics)
            return HTMLResponse(content=html)
        except TemplateError as e:
            raise HTTPException(status_code=500, detail=str(e))

    # No digest - check if we have messages
    msg_count = _get_messages_count_for_date(conn, target_date)
    processed_count = _get_processed_count_for_date(conn, target_date)
    conn.close()

    if msg_count == 0:
        raise HTTPException(status_code=404, detail=f"No messages for {target_date}")

    if processed_count == 0:
        # Have unprocessed messages - return loading state
        return HTMLResponse(
            content=f"""
            <div style="text-align: center; padding: 40px;">
                <h2>Generating digest for {target_date}...</h2>
                <p>Found {msg_count} unprocessed messages.</p>
                <p>Use: <code>my-email summarize --date {target_date}</code></p>
            </div>
            """,
            status_code=202,
        )

    # Have processed messages but no digest - build it
    try:
        digest = build_digest(get_connection(), target_date)
        active_topics = get_active_topics(get_connection(), target_date)
        html = build_html_digest(digest, active_topics)
        return HTMLResponse(content=html)
    except TemplateError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate/{target_date}")
async def generate_digest(target_date: str, background_tasks: BackgroundTasks):
    """
    Trigger sync + summarize + digest generation for a date.

    Returns immediately with task status. Check status via /api/status/{date}.
    """
    # Check if already running
    task_info = _task_status.get(target_date, {})
    if task_info.get("status") == "running":
        return {"status": "already_running", "date": target_date}

    # Trigger background task in thread pool
    _task_status[target_date] = {"status": "pending"}
    _executor.submit(_process_single_date, target_date)

    return {"status": "started", "date": target_date}


@app.get("/api/status/{target_date}")
async def get_task_status(target_date: str):
    """
    Get the status of a generation task.
    """
    task_info = _task_status.get(target_date, {"status": "not_started"})
    return {"date": target_date, **task_info}


def create_app() -> FastAPI:
    """
    Factory function to create the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    return app