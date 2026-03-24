#!/usr/bin/env python3
"""CLI interface for py-invest investment analysis."""

import argparse
import asyncio
import sys
from datetime import datetime
from typing import Optional


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
        from agents.orchestrator import SimpleAgentOrchestrator
        from modules.report_generator.formatter import ReportFormatter, ReportFormat

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
                print(f"✓ 分析完成", file=sys.stderr)
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


def cmd_analyze(args: argparse.Namespace) -> int:
    """Handle the 'analyze' command."""
    lang = "en" if args.en else "zh"
    return asyncio.run(analyze_stock(args.code, args.query, args.verbose, lang))


def cmd_version(args: argparse.Namespace) -> int:
    """Handle the 'version' command."""
    print("py-invest v0.1.0")
    return 0


def cmd_daily(args: argparse.Namespace) -> int:
    """Handle the 'daily' command - run daily analysis and send email."""
    from scheduler.daily_job import run_daily_analysis

    result = asyncio.run(run_daily_analysis(dry_run=args.dry_run))

    if result.success:
        if result.error == "Not a trading day":
            print(f"Skipping: {result.error}")
            return 0

        print(f"Analysis complete: {result.stocks_analyzed} stocks analyzed")
        if result.stocks_failed > 0:
            print(f"  Failed: {result.stocks_failed} stocks")
        print(f"Changes detected: {result.changes_detected} stocks with significant changes")
        if args.dry_run:
            print("Email: DRY RUN (not sent)")
        else:
            print(f"Email sent: {result.email_sent}")
        return 0
    else:
        print(f"Analysis failed: {result.error}", file=sys.stderr)
        return 1


def cmd_task_add(args: argparse.Namespace) -> int:
    """Handle the 'task add' command - add analysis tasks."""
    from storage import init_db, save_analysis_task, get_active_stocks, sync_stock_configs
    from config.settings import load_config

    init_db()

    # Sync stocks from config to get names
    try:
        config = load_config()
        stock_dicts = [{"code": s.code, "name": s.name} for s in config.stocks]
        sync_stock_configs(stock_dicts)
    except Exception:
        pass  # Config might not exist

    # Build stock name map
    stock_names = {s.stock_code: s.stock_name for s in get_active_stocks()}

    added = 0
    for code in args.codes:
        name = stock_names.get(code, "")
        task_id = save_analysis_task(stock_code=code, stock_name=name, priority=args.priority)
        print(f"Added task #{task_id}: {code}" + (f" ({name})" if name else ""))
        added += 1

    print(f"\nTotal tasks added: {added}")
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    """Handle the 'task list' command - list analysis tasks."""
    from storage import init_db, get_pending_tasks

    init_db()

    tasks = get_pending_tasks(limit=args.limit)

    if not tasks:
        print("No pending tasks")
        return 0

    print(f"Pending tasks ({len(tasks)}):\n")
    for task in tasks:
        name = f" ({task.stock_name})" if task.stock_name else ""
        print(f"  #{task.id}: {task.stock_code}{name} [priority={task.priority}]")

    return 0


def cmd_worker_run(args: argparse.Namespace) -> int:
    """Handle the 'worker run' command - run the analysis worker."""
    from scheduler.worker import run_worker

    print("Starting analysis worker...")
    if args.once:
        print("Running once (processing pending tasks)")
    else:
        print("Running in continuous mode (Ctrl+C to stop)")

    results = asyncio.run(run_worker(once=args.once, max_tasks=args.max_tasks))

    if results:
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        print(f"\nWorker complete: {successful} succeeded, {failed} failed")
    else:
        print("No tasks processed")

    return 0


def cmd_sender_run(args: argparse.Namespace) -> int:
    """Handle the 'sender run' command - run the email sender."""
    from notifier import EmailSender, EmailConfig
    from config.settings import load_config

    try:
        config = load_config()
    except Exception as e:
        print(f"Failed to load config: {e}", file=sys.stderr)
        return 1

    if not config.email.recipient:
        print("No recipient configured", file=sys.stderr)
        return 1

    email_config = EmailConfig(
        smtp_host=config.email.smtp_host,
        smtp_port=config.email.smtp_port,
        sender=config.email.sender,
        password=config.email.password,
        recipient=config.email.recipient,
    )

    sender = EmailSender(email_config)

    print("Processing pending emails...")
    successful, failed = asyncio.run(sender.send_pending_emails())

    print(f"Sent: {successful} emails")
    if failed > 0:
        print(f"Failed: {failed} emails")
        return 1

    return 0


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="py-invest",
        description="AI-powered investment analysis tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s analyze sh600519 "综合分析"
  %(prog)s analyze AAPL "估值分析" -v
  %(prog)s analyze 00700.HK "技术分析"
  %(prog)s daily                  # Run daily analysis and send email
  %(prog)s daily --dry-run        # Print email without sending
  %(prog)s task add AAPL TSLA     # Add analysis tasks
  %(prog)s task list              # List pending tasks
  %(prog)s worker --once          # Process pending tasks once
  %(prog)s sender                 # Send pending emails
  %(prog)s version
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a stock",
        description="Run investment analysis on a specified stock"
    )
    analyze_parser.add_argument(
        "code",
        help="Stock ticker symbol (e.g., sh600519, AAPL, 00700.HK)"
    )
    analyze_parser.add_argument(
        "query",
        nargs="?",
        default="综合分析",
        help="Analysis request (default: 综合分析)"
    )
    analyze_parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress"
    )
    analyze_parser.add_argument(
        "--en",
        action="store_true",
        help="Output report in English (default: Chinese)"
    )
    analyze_parser.set_defaults(func=cmd_analyze)

    # version command
    version_parser = subparsers.add_parser(
        "version",
        help="Show version info"
    )
    version_parser.set_defaults(func=cmd_version)

    # daily command
    daily_parser = subparsers.add_parser(
        "daily",
        help="Run daily analysis and send email",
        description="Run daily stock analysis for configured stocks and send email report"
    )
    daily_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print email content without sending"
    )
    daily_parser.set_defaults(func=cmd_daily)

    # task command group
    task_parser = subparsers.add_parser(
        "task",
        help="Manage analysis tasks",
        description="Add, list, or manage background analysis tasks"
    )
    task_subparsers = task_parser.add_subparsers(dest="task_command", help="Task commands")

    # task add
    task_add_parser = task_subparsers.add_parser(
        "add",
        help="Add analysis tasks",
        description="Add one or more stocks to the analysis queue"
    )
    task_add_parser.add_argument(
        "codes",
        nargs="+",
        help="Stock ticker symbols (e.g., AAPL TSLA NVDA)"
    )
    task_add_parser.add_argument(
        "-p", "--priority",
        type=int,
        default=0,
        help="Task priority (higher = more urgent)"
    )
    task_add_parser.set_defaults(func=cmd_task_add)

    # task list
    task_list_parser = task_subparsers.add_parser(
        "list",
        help="List pending tasks",
        description="Show pending analysis tasks"
    )
    task_list_parser.add_argument(
        "-l", "--limit",
        type=int,
        default=20,
        help="Maximum number of tasks to show"
    )
    task_list_parser.set_defaults(func=cmd_task_list)

    # worker command
    worker_parser = subparsers.add_parser(
        "worker",
        help="Run background analysis worker",
        description="Process analysis tasks from the queue"
    )
    worker_parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (default: continuous)"
    )
    worker_parser.add_argument(
        "--max-tasks",
        type=int,
        default=10,
        help="Maximum tasks to process per run"
    )
    worker_parser.set_defaults(func=cmd_worker_run)

    # sender command
    sender_parser = subparsers.add_parser(
        "sender",
        help="Run email sender",
        description="Send pending emails from the queue"
    )
    sender_parser.set_defaults(func=cmd_sender_run)

    # Parse and execute
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Handle task subcommand
    if args.command == "task":
        if not hasattr(args, "task_command") or not args.task_command:
            task_parser.print_help()
            return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
