"""
CLI entry point.

Commands:
  sync        Pull new messages from Gmail into local SQLite.
  summarize   Run LLM summarization on unprocessed messages.
  digest      Aggregate summaries into a daily digest JSON.
  show        Pretty-print the digest for a given date.

Typical daily workflow:
  my-email sync
  my-email summarize --date 2026-03-19
  my-email digest    --date 2026-03-19
  my-email show      --date 2026-03-19
"""

import json
import logging
from datetime import date as Date

import click
import structlog

from my_email.config import settings
from my_email.db.repository import (
    get_connection,
    init_db,
    get_unprocessed_messages,
    save_summary,
    save_digest,
)


def _setup_logging() -> None:
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
    )


def _today() -> str:
    return Date.today().strftime("%Y-%m-%d")


@click.group()
def cli() -> None:
    """my-email: Gmail newsletter digest tool."""
    _setup_logging()
    init_db()


# ── sync ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--full", is_flag=True, help="Force full re-sync, ignoring stored historyId.")
def sync(full: bool) -> None:
    """Pull new Gmail messages into local DB."""
    from my_email.gmail.sync import initial_sync, incremental_sync
    from my_email.db.repository import get_sync_state

    conn = get_connection()
    state = get_sync_state(conn)

    if full or not state:
        click.echo("Running full sync…")
        count, history_id = initial_sync(conn)
    else:
        click.echo(f"Running incremental sync (historyId={state['history_id']})…")
        count, history_id = incremental_sync(conn)

    conn.close()
    click.echo(f"Done. {count} new messages inserted. historyId={history_id}")


# ── summarize ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--date", "target_date", default=None, help="YYYY-MM-DD (default: today)")
@click.option("--limit", default=50, show_default=True, help="Max messages to process per run.")
def summarize(target_date: str | None, limit: int) -> None:
    """Run LLM summarization on unprocessed messages."""
    from my_email.llm.summarizer import summarize_message

    if not target_date:
        target_date = _today()

    conn = get_connection()
    rows = get_unprocessed_messages(conn, target_date)

    if not rows:
        click.echo(f"No unprocessed messages for {target_date}.")
        conn.close()
        return

    rows = rows[:limit]
    click.echo(f"Summarizing {len(rows)} message(s) for {target_date}…")

    ok, fail = 0, 0
    for row in rows:
        try:
            summary = summarize_message(
                subject=row["subject"] or "",
                sender=row["sender"] or "",
                date=row["received_at"],
                body=row["body_text"] or "",
            )
            save_summary(conn, row["id"], summary.model_dump_json(), settings.llm_model)
            conn.commit()
            ok += 1
            click.echo(f"  ✓ [{summary.relevance}] {summary.title[:70]}")
        except Exception as e:
            fail += 1
            click.echo(f"  ✗ {row['id']}: {e}", err=True)

    conn.close()
    click.echo(f"\nDone: {ok} ok, {fail} failed.")


# ── digest ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--date", "target_date", default=None, help="YYYY-MM-DD (default: today)")
@click.option("--out", default=None, help="Write digest JSON to this file path.")
def digest(target_date: str | None, out: str | None) -> None:
    """Build and store the daily digest from summarized messages."""
    from my_email.digest.builder import build_digest

    if not target_date:
        target_date = _today()

    conn = get_connection()
    result = build_digest(conn, target_date)
    digest_json = result.model_dump_json(indent=2)
    save_digest(conn, target_date, result.model_dump_json())
    conn.commit()
    conn.close()

    if out:
        with open(out, "w") as f:
            f.write(digest_json)
        click.echo(f"Digest written to {out}")
    else:
        click.echo(digest_json)


# ── show ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--date", "target_date", default=None, help="YYYY-MM-DD (default: today)")
def show(target_date: str | None) -> None:
    """Pretty-print the daily digest."""
    from my_email.digest.builder import build_digest

    if not target_date:
        target_date = _today()

    conn = get_connection()
    result = build_digest(conn, target_date)
    conn.close()

    click.echo(f"\n{'='*60}")
    click.echo(f"  Daily Digest — {result.date}")
    click.echo(f"{'='*60}")
    click.echo(
        f"  Emails: {result.total_emails}  |  High relevance: {result.high_relevance_count}"
    )
    if result.top_topics:
        click.echo(f"  Top topics: {', '.join(result.top_topics[:8])}")
    click.echo()

    for s in result.summaries:
        rel = s.get("relevance", "?").upper()
        title = s.get("title", "(unknown)")
        org = s.get("sender_org", "")
        topics = ", ".join(s.get("topics", []))
        recv = s.get("received_at", "")[:10]
        summary = s.get("summary", "")
        key_points = s.get("key_points", [])
        action_items = s.get("action_items", [])
        people = s.get("people_mentioned", [])
        links = s.get("links", [])

        click.echo(f"[{rel}] {title}")
        click.echo(f"  {org}  |  {recv}")
        click.echo(f"  Topics: {topics}")
        click.echo()
        click.echo(f"  Summary:")
        click.echo(f"  {summary}")
        click.echo()
        click.echo(f"  Key Points:")
        for pt in key_points:
            click.echo(f"    • {pt}")
        if people:
            click.echo(f"\n  People: {', '.join(people)}")
        if links:
            click.echo(f"  Links: {', '.join(links[:5])}" + ("..." if len(links) > 5 else ""))
        if action_items:
            click.echo(f"\n  ⚠️  Action Items:")
            for item in action_items:
                click.echo(f"    • {item}")
        click.echo()
        click.echo("-" * 60)
