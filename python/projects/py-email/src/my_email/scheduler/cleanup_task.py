"""Auto-cleanup background task."""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone

import structlog

from my_email.db.repository import cleanup_old_messages, get_connection, get_setting

log = structlog.get_logger()


def seconds_until_midnight() -> int:
    """
    Calculate seconds until next midnight UTC.

    Returns:
        Number of seconds until midnight.
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    # Calculate midnight of the next day
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((tomorrow - now).total_seconds())


async def run_cleanup(db_conn: sqlite3.Connection | None = None) -> dict:
    """
    Run a single cleanup of old messages.

    Args:
        db_conn: Optional database connection. If None, creates a new one.

    Returns:
        Cleanup result dict with 'deleted' key.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_connection()
        should_close = True

    try:
        retention_days = int(get_setting(db_conn, "retention_days", default="7"))
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        deleted = cleanup_old_messages(
            db_conn, retention_days=retention_days, current_date=current_date
        )
        db_conn.commit()

        result = {"deleted": deleted}
        log.info("cleanup_task.done", **result)
        return result

    finally:
        if should_close:
            db_conn.close()


async def start_cleanup_scheduler() -> None:
    """
    Start the daily cleanup scheduler.

    Runs cleanup every day at midnight UTC.
    """
    while True:
        wait_seconds = seconds_until_midnight()
        log.info("cleanup_scheduler.waiting", seconds_until_midnight=wait_seconds)
        await asyncio.sleep(wait_seconds)

        try:
            await run_cleanup()
        except Exception as e:
            log.error("cleanup_scheduler.error", error=str(e))
