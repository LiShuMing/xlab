#!/usr/bin/env python3
"""Click CLI interface for Invest analysis."""

from __future__ import annotations

import asyncio
import sys

import click


async def analyze_stock(
    stock_code: str,
    query: str,
    verbose: bool = False,
    lang: str = "zh",
) -> int:
    """Run investment analysis on a stock.

    Args:
        stock_code: Stock ticker symbol (e.g., sh600519, AAPL).
        query: Analysis request (e.g., "综合分析", "技术分析").
        verbose: Show detailed progress.
        lang: Output language ("zh" for Chinese, "en" for English).

    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        from backend.invest.agents.orchestrator import SimpleAgentOrchestrator
        from backend.invest.modules.report_generator.formatter import ReportFormat, ReportFormatter

        if verbose:
            print(f"正在分析股票：{stock_code}", file=sys.stderr)
            print(f"分析请求：{query}", file=sys.stderr)
            print(file=sys.stderr)

        orchestrator = SimpleAgentOrchestrator(lang=lang)
        state = await orchestrator.analyze(stock_code, query)

        if state.error:
            print(f"分析失败：{state.error}", file=sys.stderr)
            return 1

        if state.report:
            # Output the markdown report to stdout
            print(ReportFormatter.format(state.report, ReportFormat.MARKDOWN, lang=lang))

            if verbose:
                print(file=sys.stderr)
                print("✓ 分析完成", file=sys.stderr)
                print(f"  股票代码：{state.report.stock_code}", file=sys.stderr)
                print(f"  目标价格：{state.report.target_price or 'N/A'}", file=sys.stderr)
                print(f"  评级：{state.report.rating or 'N/A'}", file=sys.stderr)
                print(f"  章节数：{len(state.report.sections)}", file=sys.stderr)
        else:
            # Fallback to final_response for backward compatibility
            if state.final_response:
                print(state.final_response)
            else:
                print("分析完成，但没有生成报告", file=sys.stderr)
                return 1

        return 0

    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        if verbose:
            import traceback

            traceback.print_exc(file=sys.stderr)
        return 1


@click.group()
def cli() -> None:
    """Investment intelligence: analyze stocks, run daily reports, manage tasks."""


@cli.command()
@click.argument("code")
@click.argument("query", default="综合分析")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed progress")
@click.option("--en", "english", is_flag=True, help="Output report in English")
def analyze(code: str, query: str, verbose: bool, english: bool) -> None:
    """Analyze a stock and print the report."""
    lang = "en" if english else "zh"
    rc = asyncio.run(analyze_stock(code, query, verbose, lang))
    if rc != 0:
        raise SystemExit(rc)


async def _task_add(codes: tuple[str, ...] | list[str], priority: int, emit) -> None:
    """Add Invest analysis tasks through the unified business database."""
    from backend._shared.storage import business_uow
    from backend.invest.config.settings import load_config
    from backend.invest.service import get_active_stocks, save_analysis_task, sync_stock_configs

    async with business_uow() as session:
        try:
            config = load_config()
            stock_dicts = [{"code": s.code, "name": s.name} for s in config.stocks]
            await sync_stock_configs(session, stock_dicts)
        except Exception:
            pass

        stock_names = {s.stock_code: s.stock_name for s in await get_active_stocks(session)}
        added = 0
        for code in codes:
            name = stock_names.get(code, "")
            task_id = await save_analysis_task(
                session,
                stock_code=code,
                stock_name=name,
                priority=priority,
            )
            emit(f"Added task #{task_id}: {code}" + (f" ({name})" if name else ""))
            added += 1

    emit(f"\nTotal tasks added: {added}")


async def _task_list(limit: int, emit) -> None:
    """List Invest analysis tasks through the unified business database."""
    from backend._shared.storage import business_uow
    from backend.invest.service import get_pending_tasks

    async with business_uow() as session:
        tasks = await get_pending_tasks(session, limit=limit)

    if not tasks:
        emit("No pending tasks")
        return

    emit(f"Pending tasks ({len(tasks)}):\n")
    for task_item in tasks:
        name = f" ({task_item.stock_name})" if task_item.stock_name else ""
        emit(f"  #{task_item.id}: {task_item.stock_code}{name} [priority={task_item.priority}]")


@cli.command("daily")
@click.option("--dry-run", is_flag=True, help="Print email without sending")
def daily(dry_run: bool) -> None:
    """Run daily analysis and send email report."""
    from backend.invest.scheduler.daily_job import run_daily_analysis

    result = asyncio.run(run_daily_analysis(dry_run=dry_run))
    if result.success:
        if result.error == "Not a trading day":
            click.echo(f"Skipping: {result.error}")
            return
        click.echo(f"Analysis complete: {result.stocks_analyzed} stocks analyzed")
        if result.stocks_failed > 0:
            click.echo(f"  Failed: {result.stocks_failed} stocks")
        click.echo(f"Changes detected: {result.changes_detected} stocks with significant changes")
        if dry_run:
            click.echo("Email: DRY RUN (not sent)")
        else:
            click.echo(f"Email sent: {result.email_sent}")
    else:
        raise click.ClickException(f"Analysis failed: {result.error}")


@cli.group()
def task() -> None:
    """Manage background analysis tasks."""


@task.command("add")
@click.argument("codes", nargs=-1, required=True)
@click.option("-p", "--priority", type=int, default=0, help="Task priority")
def task_add(codes: tuple[str, ...], priority: int) -> None:
    """Add stocks to the analysis queue."""
    asyncio.run(_task_add(codes, priority, click.echo))


@task.command("list")
@click.option("-l", "--limit", type=int, default=20, help="Max tasks to show")
def task_list(limit: int) -> None:
    """List pending analysis tasks."""
    asyncio.run(_task_list(limit, click.echo))


@cli.command()
@click.option("--once", is_flag=True, help="Run once and exit")
@click.option("--max-tasks", type=int, default=10, help="Max tasks per run")
def worker(once: bool, max_tasks: int) -> None:
    """Run the background analysis worker."""
    from backend.invest.scheduler.worker import run_worker

    click.echo("Starting analysis worker...")
    if once:
        click.echo("Running once (processing pending tasks)")
    else:
        click.echo("Running in continuous mode (Ctrl+C to stop)")

    results = asyncio.run(run_worker(once=once, max_tasks=max_tasks))
    if results:
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        click.echo(f"\nWorker complete: {successful} succeeded, {failed} failed")
    else:
        click.echo("No tasks processed")


@cli.command()
def sender() -> None:
    """Send pending emails from the queue."""
    from backend.invest.config.settings import load_config
    from backend.invest.notifier import EmailConfig, EmailSender

    try:
        config = load_config()
    except Exception as e:
        raise click.ClickException(f"Failed to load config: {e}") from e

    if not config.email.recipient:
        raise click.ClickException("No recipient configured")

    email_config = EmailConfig(
        smtp_host=config.email.smtp_host,
        smtp_port=config.email.smtp_port,
        sender=config.email.sender,
        password=config.email.password,
        recipient=config.email.recipient,
    )
    sender_obj = EmailSender(email_config)
    click.echo("Processing pending emails...")
    successful, failed = asyncio.run(sender_obj.send_pending_emails())
    click.echo(f"Sent: {successful} emails")
    if failed > 0:
        raise click.ClickException(f"Failed: {failed} emails")


if __name__ == "__main__":
    cli()
