"""Auto-sync background task."""

from __future__ import annotations

import asyncio
import sqlite3

import structlog

from my_email.db.repository import get_connection, get_setting, save_setting
from my_email.gmail.sync import build_service, sync_messages
from my_email.llm.summarizer import summarize_message

log = structlog.get_logger()


async def run_sync(db_conn: sqlite3.Connection | None = None) -> dict:
    """
    Run a single sync and summarize new messages.

    Args:
        db_conn: Optional database connection. If None, creates a new one.

    Returns:
        Sync result dict with 'synced', 'summarized', 'errors' keys.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_connection()
        should_close = True

    try:
        service = build_service()
        result = sync_messages(db_conn, service)

        # Summarize new messages
        summarized = 0
        errors = result.get("errors", 0)

        if result["synced"] > 0:
            # Get messages without summaries
            cursor = db_conn.execute(
                """SELECT id, subject, sender, received_at, body_text
                   FROM messages
                   WHERE summary_json IS NULL AND body_text IS NOT NULL
                   ORDER BY received_at DESC"""
            )
            for row in cursor.fetchall():
                try:
                    summary = summarize_message(
                        subject=row["subject"],
                        sender=row["sender"],
                        date=row["received_at"],
                        body=row["body_text"][:8000],  # Truncate to avoid token limits
                    )
                    import json
                    from my_email.db.repository import save_summary
                    save_summary(db_conn, row["id"], json.dumps(summary.model_dump()))
                    summarized += 1
                except Exception as e:
                    log.warning("sync_task.summarize_error", id=row["id"], error=str(e))
                    errors += 1

            db_conn.commit()

        result["summarized"] = summarized
        result["errors"] = errors
        log.info("sync_task.done", **result)
        return result

    finally:
        if should_close:
            db_conn.close()


async def start_sync_scheduler() -> None:
    """
    Start the periodic sync scheduler.

    Runs sync every auto_sync_interval_minutes (from settings).
    Performs an initial sync immediately on startup.
    """
    # Run initial sync immediately
    try:
        await run_sync()
    except Exception as e:
        log.error("sync_scheduler.initial_error", error=str(e))

    while True:
        try:
            db_conn = get_connection()
            interval = int(get_setting(db_conn, "auto_sync_interval_minutes", default="30"))
            db_conn.close()
        except Exception:
            interval = 30

        log.info("sync_scheduler.waiting", interval_minutes=interval)
        await asyncio.sleep(interval * 60)

        try:
            await run_sync()
        except Exception as e:
            log.error("sync_scheduler.error", error=str(e))