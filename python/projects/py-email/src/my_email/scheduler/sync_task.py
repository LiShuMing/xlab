"""Auto-sync background task."""

from __future__ import annotations

import asyncio
import json
import sqlite3

import structlog

from my_email.db.repository import (
    get_connection,
    get_setting,
    save_setting,
    save_summary,
    save_thread_summary,
    get_unsummarized_threads,
)
from my_email.gmail.sync import build_service, sync_messages
from my_email.llm.summarizer import summarize_message, summarize_thread
from my_email.llm.thread_aggregator import ThreadAggregator

log = structlog.get_logger()

# Max threads to summarize per batch
SUMMARY_BATCH_SIZE = 5


async def run_sync_only(db_conn: sqlite3.Connection | None = None) -> dict:
    """
    Run sync without summarization (fast).

    Args:
        db_conn: Optional database connection.

    Returns:
        Sync result dict.
    """
    should_close = False
    if db_conn is None:
        db_conn = get_connection()
        should_close = True

    try:
        service = build_service()
        result = sync_messages(db_conn, service)
        log.info("sync_task.sync_done", **result)
        return result
    finally:
        if should_close:
            db_conn.close()


async def run_summarization_batch(limit: int = SUMMARY_BATCH_SIZE) -> int:
    """
    Summarize a batch of messages without summaries.

    Args:
        limit: Max messages to process.

    Returns:
        Number of messages summarized.
    """
    db_conn = get_connection()
    try:
        # Get messages without summaries (limit to batch size)
        cursor = db_conn.execute(
            """SELECT id, subject, sender, received_at, body_text
               FROM messages
               WHERE summary_json IS NULL AND body_text IS NOT NULL
               ORDER BY received_at DESC
               LIMIT ?""",
            (limit,),
        )
        rows = cursor.fetchall()

        if not rows:
            return 0

        summarized = 0
        for row in rows:
            try:
                summary = summarize_message(
                    subject=row["subject"],
                    sender=row["sender"],
                    date=row["received_at"],
                    body=row["body_text"][:8000],
                )
                save_summary(db_conn, row["id"], json.dumps(summary.model_dump()))
                db_conn.commit()
                summarized += 1
                log.info("sync_task.summarized", id=row["id"])
            except Exception as e:
                log.warning("sync_task.summarize_error", id=row["id"], error=str(e))

        return summarized
    finally:
        db_conn.close()


async def run_sync(db_conn: sqlite3.Connection | None = None) -> dict:
    """
    Run a single sync (without summarization for speed).

    Summarization runs separately in background.

    Args:
        db_conn: Optional database connection.

    Returns:
        Sync result dict.
    """
    result = await run_sync_only(db_conn)
    result["summarized"] = 0
    return result


async def start_summarization_worker() -> None:
    """Background worker that continuously summarizes messages."""
    # Wait a bit before starting summarization (let server start first)
    await asyncio.sleep(10)

    while True:
        try:
            # Run summarization in a thread pool to not block
            summarized = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _run_summarization_batch_sync()
            )
            if summarized == 0:
                await asyncio.sleep(60)
            else:
                await asyncio.sleep(2)
        except Exception as e:
            log.error("summarization_worker.error", error=str(e))
            await asyncio.sleep(30)


def _run_summarization_batch_sync(limit: int = SUMMARY_BATCH_SIZE) -> int:
    """Synchronous version for thread pool execution."""
    db_conn = get_connection()
    try:
        # Get thread groups for summarization
        thread_groups = get_unsummarized_threads(db_conn, limit=limit)

        if not thread_groups:
            return 0

        summarized = 0
        aggregator = ThreadAggregator()

        for group in thread_groups:
            messages = group["messages"]
            try:
                if len(messages) == 1:
                    # Single message - use regular summarization
                    msg = messages[0]
                    summary = summarize_message(
                        subject=msg["subject"],
                        sender=msg["sender"],
                        date=msg["received_at"],
                        body=msg["body_text"][:8000],
                    )
                    save_summary(db_conn, msg["id"], json.dumps(summary.model_dump()))
                    summarized += 1
                    log.info("sync_task.summarized", id=msg["id"])
                else:
                    # Multiple messages - use thread summarization
                    # Use the aggregator to format the thread body
                    aggregated = aggregator.aggregate(messages)[0]
                    summary = summarize_thread(
                        subject=aggregated["base_subject"],
                        message_count=aggregated["message_count"],
                        date_range=aggregated["date_range"],
                        combined_body=aggregated["combined_body"],
                    )
                    # Save the same summary for all messages in the thread
                    updated = save_thread_summary(
                        db_conn,
                        aggregated["message_ids"],
                        json.dumps(summary.model_dump()),
                    )
                    summarized += updated
                    log.info(
                        "sync_task.thread_summarized",
                        thread_subject=aggregated["base_subject"][:60],
                        message_count=aggregated["message_count"],
                        updated=updated,
                    )

                db_conn.commit()
            except Exception as e:
                log.warning(
                    "sync_task.summarize_error",
                    thread_subject=group["thread_subject"][:60],
                    error=str(e),
                )

        return summarized
    finally:
        db_conn.close()


async def start_sync_scheduler() -> None:
    """
    Start the periodic sync scheduler.

    Runs sync every auto_sync_interval_minutes (from settings).
    Performs an initial sync immediately on startup.
    """
    # Run initial sync immediately (without blocking)
    try:
        await run_sync_only()
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
            await run_sync_only()
        except Exception as e:
            log.error("sync_scheduler.error", error=str(e))