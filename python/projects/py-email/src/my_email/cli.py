"""
CLI entry point.

Commands:
  sync        Pull new messages from Gmail into local SQLite.
  summarize   Run LLM summarization on unprocessed messages.
  digest      Aggregate summaries into a daily digest JSON.
  show        Pretty-print the digest for a given date.
  topics      Show topic arc table (ongoing discussion threads).
  server      Start web server to browse email digests.

Typical daily workflow:
  my-email sync
  my-email summarize --date 2026-03-19
  my-email digest    --date 2026-03-19 [--html [--open]]
  my-email show      --date 2026-03-19
  my-email topics

Server mode:
  my-email server --host 127.0.0.1 --port 8080
"""

from __future__ import annotations

import logging
import os
import webbrowser
from datetime import date as Date
from typing import Any

import click
import structlog

from my_email.config import settings
from my_email.db.repository import (
    get_connection,
    init_db,
    get_unprocessed_messages,
    save_digest,
)


def _setup_logging() -> None:
    """Configure structlog with the application log level."""
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
    )


def _today() -> str:
    """Return today's date as YYYY-MM-DD string."""
    return Date.today().strftime("%Y-%m-%d")


def _format_summary_display(summary: dict[str, Any]) -> list[str]:
    """
    Format a single email summary for terminal display.

    Args:
        summary: Email summary dict from DailyDigest.

    Returns:
        List of formatted lines for display.
    """
    lines: list[str] = []

    rel = summary.get("relevance", "?").upper()
    title = summary.get("title", "(unknown)")
    org = summary.get("sender_org", "")
    topics = ", ".join(summary.get("topics", []))
    recv = summary.get("received_at", "")[:10]
    summary_text = summary.get("summary", "")
    key_points = summary.get("key_points", [])
    action_items = summary.get("action_items", [])
    people = summary.get("people_mentioned", [])
    links = summary.get("links", [])

    lines.append(f"[{rel}] {title}")
    lines.append(f"  {org}  |  {recv}")
    lines.append(f"  Topics: {topics}")
    lines.append("")
    lines.append("  Summary:")
    lines.append(f"  {summary_text}")
    lines.append("")
    lines.append("  Key Points:")
    for pt in key_points:
        lines.append(f"    • {pt}")

    if people:
        lines.append(f"\n  People: {', '.join(people)}")

    if links:
        lines.append(f"  Links: {', '.join(links[:5])}" + ("..." if len(links) > 5 else ""))

    if action_items:
        lines.append("\n  ⚠️  Action Items:")
        for item in action_items:
            lines.append(f"    • {item}")

    return lines


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
@click.option("--no-filter", is_flag=True, help="Disable email filtering (keep starrocks, auto-replies).")
@click.option("--no-aggregate", is_flag=True, help="Disable thread aggregation (process each message separately).")
def summarize(target_date: str | None, limit: int, no_filter: bool, no_aggregate: bool) -> None:
    """
    Run LLM summarization on unprocessed messages.

    By default, this command:
    - Filters out StarRocks-related emails and auto-reply messages
    - Aggregates emails in the same thread for unified summarization
    - Uses thread-aware prompts for multi-message conversations

    Use --no-filter to include all emails.
    Use --no-aggregate to process each message independently.
    """
    from my_email.llm import (
        EmailFilter,
        ThreadAggregator,
        summarize_message,
        summarize_thread,
        LLMSummarizationError,
    )
    from my_email.db.repository import save_summary, save_thread_summary

    if not target_date:
        target_date = _today()

    conn = get_connection()
    rows = get_unprocessed_messages(conn, target_date)

    if not rows:
        click.echo(f"No unprocessed messages for {target_date}.")
        conn.close()
        return

    # Convert rows to dicts for filtering/aggregation
    messages = [dict(row) for row in rows]

    # Step 1: Filter unwanted emails
    filter_stats: dict[str, int] = {}
    if not no_filter:
        email_filter = EmailFilter(
            exclude_starrocks=True,
            exclude_auto_reply=True,
            exclude_noreply=False,
        )
        messages, filter_stats = email_filter.filter_messages(messages)
        if filter_stats:
            click.echo(f"Filtered {sum(filter_stats.values())} emails: {filter_stats}")

    if not messages:
        click.echo(f"No messages remaining after filtering for {target_date}.")
        conn.close()
        return

    # Step 2: Aggregate threads
    aggregator = ThreadAggregator(
        use_thread_id=True,
        use_subject_similarity=True,
        min_group_size=1,
    )
    aggregated = aggregator.aggregate(messages)

    # Limit after aggregation
    aggregated = aggregated[:limit]

    # Count threads vs singles
    thread_count = sum(1 for a in aggregated if a.get("is_thread"))
    single_count = len(aggregated) - thread_count
    click.echo(f"Summarizing {len(aggregated)} item(s) for {target_date} ({thread_count} threads, {single_count} singles)…")

    ok, fail = 0, 0
    for group in aggregated:
        try:
            if group.get("is_thread"):
                # Thread summarization
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
                click.echo(f"  ✓ [{summary.relevance}] {summary.title[:70]} ({group['message_count']} msgs)")
            else:
                # Single message summarization
                msg = group["messages"][0]
                summary = summarize_message(
                    subject=msg.get("subject", "") or "",
                    sender=msg.get("sender", "") or "",
                    date=msg.get("received_at", ""),
                    body=msg.get("body_text", "") or "",
                )
                save_summary(conn, msg["id"], summary.model_dump_json(), settings.llm_model)
                click.echo(f"  ✓ [{summary.relevance}] {summary.title[:70]}")

            conn.commit()
            ok += 1
        except LLMSummarizationError as e:
            fail += 1
            ids = group.get("message_ids", ["?"])
            click.echo(f"  ✗ {ids[0]}: {e}", err=True)
        except Exception as e:
            fail += 1
            ids = group.get("message_ids", ["?"])
            click.echo(f"  ✗ {ids[0]}: {e}", err=True)

    conn.close()
    click.echo(f"\nDone: {ok} ok, {fail} failed.")


# ── digest ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--date", "target_date", default=None, help="YYYY-MM-DD (default: today)")
@click.option("--out", default=None, help="Write digest JSON to this file path.")
@click.option("--output-dir", default=None, help="Write JSON + HTML to <dir>/digest-<date>.*")
@click.option("--html", "emit_html", is_flag=True, help="Also write an HTML digest file.")
@click.option("--open", "open_browser", is_flag=True, help="Open the HTML file in a browser after writing.")
def digest(
    target_date: str | None,
    out: str | None,
    output_dir: str | None,
    emit_html: bool,
    open_browser: bool,
) -> None:
    """Build and store the daily digest from summarized messages."""
    from my_email.digest.builder import build_digest
    from my_email.db.topic_repository import upsert_topic_tracks, get_active_topics
    from my_email.digest.renderer import build_html_digest, TemplateError

    if not target_date:
        target_date = _today()

    conn = get_connection()
    result = build_digest(conn, target_date)
    digest_json = result.model_dump_json(indent=2)
    save_digest(conn, target_date, result.model_dump_json())

    # Upsert topic arcs — must happen before conn.close()
    upsert_topic_tracks(conn, target_date, result.topic_clusters)

    # Prefetch active topics for HTML render before closing conn
    active_topics = get_active_topics(conn, target_date) if emit_html else []

    conn.commit()
    conn.close()

    # Determine output paths
    html_path: str | None = None
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        json_path = os.path.join(output_dir, f"digest-{target_date}.json")
        with open(json_path, "w") as f:
            f.write(digest_json)
        click.echo(f"Digest written to {json_path}")
        if emit_html:
            html_path = os.path.join(output_dir, f"digest-{target_date}.html")
    elif out:
        with open(out, "w") as f:
            f.write(digest_json)
        click.echo(f"Digest written to {out}")
        if emit_html:
            html_path = os.path.splitext(out)[0] + ".html"
    else:
        click.echo(digest_json)
        if emit_html:
            html_path = f"digest-{target_date}.html"

    if emit_html and html_path:
        try:
            html = build_html_digest(result, active_topics)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            click.echo(f"HTML digest written to {html_path}")
            if open_browser:
                webbrowser.open(f"file://{os.path.abspath(html_path)}")
        except TemplateError as e:
            click.echo(f"Warning: Could not generate HTML: {e}", err=True)


# ── topics ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--days", default=30, show_default=True, help="Look-back window in days.")
@click.option("--top", default=20, show_default=True, help="Max topics to show.")
@click.option("--date", "as_of_date", default=None, help="YYYY-MM-DD reference date (default: today)")
def topics(days: int, top: int, as_of_date: str | None) -> None:
    """Show ongoing topic threads with arc data and trend indicators."""
    from my_email.db.topic_repository import get_active_topics

    if not as_of_date:
        as_of_date = _today()

    conn = get_connection()
    rows = get_active_topics(conn, as_of_date, window_days=days, top_n=top)
    conn.close()

    if not rows:
        click.echo("No topics tracked yet. Run 'my-email digest' first.")
        return

    click.echo(f"\n{'='*72}")
    click.echo(f"  Topic Arcs  (as of {as_of_date}, last {days} days)")
    click.echo(f"{'='*72}")
    click.echo(f"  {'TOPIC':<30} {'TREND':>5}  {'DAYS':>4}  {'TOTAL':>5}  {'PEAK':>5}  FIRST SEEN")
    click.echo(f"  {'-'*30} {'-'*5}  {'-'*4}  {'-'*5}  {'-'*5}  {'-'*10}")

    for row in rows:
        click.echo(
            f"  {row['topic'][:30]:<30} {row['trend_arrow']:>5}  "
            f"{row['days_active']:>4}  {row['total_mentions']:>5}  "
            f"{row['peak_count']:>5}  {row['first_seen_date']}"
        )
    click.echo()


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

    for summary in result.summaries:
        lines = _format_summary_display(summary)
        for line in lines:
            click.echo(line)
        click.echo()
        click.echo("-" * 60)


# ── server ────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
@click.option("--port", default=8080, help="Port to bind (default: 8080)")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def server(host: str, port: int, reload: bool) -> None:
    """
    Start web server to browse email digests.

    Provides a web interface to:
    - Browse all available digest dates
    - View HTML digest for a specific date
    - Trigger sync+summarize for dates without digest
    """
    try:
        import uvicorn
    except ImportError:
        click.echo("Error: uvicorn is required for server mode.", err=True)
        click.echo("Install with: pip install uvicorn", err=True)
        raise SystemExit(1)

    click.echo(f"Starting server at http://{host}:{port}")
    click.echo("Press Ctrl+C to stop")

    uvicorn.run(
        "my_email.server.app:app",
        host=host,
        port=port,
        reload=reload,
    )