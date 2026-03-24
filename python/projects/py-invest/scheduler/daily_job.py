"""Main orchestration for daily stock analysis email system.

This module implements the main daily job that:
1. Checks if today is a trading day
2. Loads config and stock list
3. Runs analysis for each stock (parallel)
4. Saves reports to storage
5. Compares with yesterday
6. Formats incremental email
7. Sends email
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from core.logger import get_logger
from config.settings import load_config, AppConfig, StockConfig

logger = get_logger("scheduler.daily_job")

# Timeout for single stock analysis (seconds)
SINGLE_STOCK_TIMEOUT = 120

# Maximum concurrent analyses
MAX_CONCURRENT_ANALYSES = 5


@dataclass
class DailyJobResult:
    """Result of daily analysis job.

    Attributes:
        success: Whether the job completed successfully.
        stocks_analyzed: Number of stocks analyzed.
        stocks_failed: Number of stocks that failed analysis.
        changes_detected: Number of stocks with significant changes.
        email_sent: Whether email was sent.
        error: Error message if job failed.
        failed_stocks: List of failed stock info.
    """

    success: bool = True
    stocks_analyzed: int = 0
    stocks_failed: int = 0
    changes_detected: int = 0
    email_sent: bool = False
    error: Optional[str] = None
    failed_stocks: list[dict[str, str]] = field(default_factory=list)


def is_trading_day(check_date: Optional[date] = None) -> bool:
    """Check if a date is a trading day.

    A trading day is a weekday that is not a Chinese holiday.
    Uses chinese_calendar package if available, otherwise falls back
    to weekday check.

    Args:
        check_date: Date to check. Defaults to today.

    Returns:
        True if the date is a trading day, False otherwise.
    """
    check_date = check_date or date.today()

    # Check if it's a weekend
    if check_date.weekday() >= 5:  # Saturday=5, Sunday=6
        logger.debug("Not a trading day: weekend", date=str(check_date))
        return False

    # Try to use chinese_calendar for holiday check
    try:
        import chinese_calendar

        # is_workday returns True for regular workdays and adjusted workdays
        # For trading days, we want to exclude weekends and holidays
        if chinese_calendar.is_holiday(check_date):
            logger.debug("Not a trading day: Chinese holiday", date=str(check_date))
            return False

        # Check if it's a weekend make-up workday (not a trading day)
        # Chinese stock market doesn't trade on weekend make-up days
        if check_date.weekday() >= 5 and chinese_calendar.is_workday(check_date):
            logger.debug("Not a trading day: weekend make-up workday", date=str(check_date))
            return False

    except ImportError:
        logger.warning(
            "chinese_calendar not installed, using weekday check only. "
            "Install with: pip install chinese_calendar"
        )
        # Fall back to just weekday check
        return check_date.weekday() < 5

    return True


async def analyze_single_stock(
    stock_code: str,
    stock_name: str,
    lang: str = "zh",
) -> dict[str, Any]:
    """Analyze a single stock.

    Args:
        stock_code: Stock ticker symbol.
        stock_name: Stock name for display.
        lang: Output language.

    Returns:
        dict with 'success', 'report' (Report object), 'error' keys.
    """
    from agents.orchestrator import SimpleAgentOrchestrator

    result: dict[str, Any] = {
        "success": False,
        "report": None,
        "error": None,
        "stock_code": stock_code,
        "stock_name": stock_name,
    }

    try:
        logger.info(
            "Starting analysis",
            stock_code=stock_code,
            stock_name=stock_name,
        )

        orchestrator = SimpleAgentOrchestrator(lang=lang)
        state = await orchestrator.analyze(stock_code, "daily_summary")

        if state.error:
            result["error"] = state.error
            logger.error(
                "Analysis failed",
                stock_code=stock_code,
                error=state.error,
            )
        elif state.report:
            result["success"] = True
            result["report"] = state.report
            logger.info(
                "Analysis complete",
                stock_code=stock_code,
                rating=state.report.rating,
                target_price=state.report.target_price,
            )
        else:
            result["error"] = "No report generated"
            logger.warning(
                "No report generated",
                stock_code=stock_code,
            )

    except asyncio.TimeoutError:
        result["error"] = f"Analysis timed out after {SINGLE_STOCK_TIMEOUT}s"
        logger.error(
            "Analysis timeout",
            stock_code=stock_code,
            timeout=SINGLE_STOCK_TIMEOUT,
        )

    except Exception as e:
        result["error"] = str(e)
        logger.exception(
            "Analysis exception",
            stock_code=stock_code,
            error=str(e),
        )

    return result


def _report_to_dict(report: Any) -> dict[str, Any]:
    """Convert Report object to dictionary for JSON serialization.

    Args:
        report: Report object from orchestrator.

    Returns:
        Dictionary representation of the report.
    """
    from modules.report_generator.types import Report
    from modules.report_generator.formatter import ReportFormatter, ReportFormat

    if not isinstance(report, Report):
        return {}

    # Use the formatter's JSON output
    json_str = ReportFormatter.format(report, ReportFormat.JSON)
    return json.loads(json_str)


async def run_daily_analysis(dry_run: bool = False) -> DailyJobResult:
    """Run daily stock analysis and send email.

    Main entry point for daily analysis. Orchestrates the full pipeline:
    1. Check trading day
    2. Load config
    3. Analyze stocks in parallel
    4. Save reports
    5. Compare with yesterday
    6. Send email

    Args:
        dry_run: If True, print email content instead of sending.

    Returns:
        DailyJobResult with analysis status.
    """
    from storage import init_db, save_report, get_report, sync_stock_configs
    from diff import compare_reports, format_incremental_email, format_email_subject
    from notifier import EmailSender, EmailConfig

    result = DailyJobResult()
    today = date.today()

    logger.info("Starting daily analysis", date=str(today), dry_run=dry_run)

    # Step 1: Check if today is a trading day
    if not is_trading_day(today):
        logger.info("Not a trading day, skipping analysis", date=str(today))
        result.success = True
        result.error = "Not a trading day"
        return result

    # Step 2: Load configuration
    try:
        config = load_config()
    except Exception as e:
        result.error = f"Failed to load config: {e}"
        logger.error("Config load failed", error=str(e))
        return result

    if not config.stocks:
        result.error = "No stocks configured"
        logger.warning("No stocks in config")
        return result

    logger.info("Loaded config", stock_count=len(config.stocks))

    # Initialize database
    init_db()

    # Sync stock configs to database
    stock_dicts = [{"code": s.code, "name": s.name} for s in config.stocks]
    sync_stock_configs(stock_dicts)

    # Step 3: Analyze stocks in parallel with timeout
    async def analyze_with_timeout(stock: StockConfig) -> dict[str, Any]:
        """Analyze stock with timeout wrapper."""
        try:
            return await asyncio.wait_for(
                analyze_single_stock(stock.code, stock.name),
                timeout=SINGLE_STOCK_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return {
                "success": False,
                "stock_code": stock.code,
                "stock_name": stock.name,
                "error": f"Timeout after {SINGLE_STOCK_TIMEOUT}s",
            }

    # Run analyses with semaphore for concurrency control
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_ANALYSES)

    async def bounded_analyze(stock: StockConfig) -> dict[str, Any]:
        async with semaphore:
            return await analyze_with_timeout(stock)

    logger.info("Starting parallel analysis", stock_count=len(config.stocks))
    analysis_results = await asyncio.gather(
        *[bounded_analyze(stock) for stock in config.stocks],
        return_exceptions=True,
    )

    # Process results
    successful_reports: list[dict[str, Any]] = []
    failed_stocks: list[dict[str, str]] = []

    for analysis_result in analysis_results:
        if isinstance(analysis_result, Exception):
            failed_stocks.append({
                "stock_code": "unknown",
                "error": str(analysis_result),
            })
            continue

        if analysis_result.get("success"):
            report = analysis_result.get("report")
            if report:
                report_dict = _report_to_dict(report)
                report_dict["stock_name"] = analysis_result.get("stock_name", "")
                successful_reports.append(report_dict)

                # Step 4: Save report to storage
                try:
                    save_report(
                        stock_code=analysis_result["stock_code"],
                        report_date=today,
                        analysis_json=json.dumps(report_dict, ensure_ascii=False),
                    )
                except Exception as e:
                    logger.error(
                        "Failed to save report",
                        stock_code=analysis_result["stock_code"],
                        error=str(e),
                    )
        else:
            failed_stocks.append({
                "stock_code": analysis_result.get("stock_code", "unknown"),
                "error": analysis_result.get("error", "Unknown error"),
            })

    result.stocks_analyzed = len(successful_reports)
    result.stocks_failed = len(failed_stocks)
    result.failed_stocks = failed_stocks

    logger.info(
        "Analysis complete",
        successful=result.stocks_analyzed,
        failed=result.stocks_failed,
    )

    # Step 5: Compare with yesterday
    yesterday = today - timedelta(days=1)
    incremental_reports = []

    for report_dict in successful_reports:
        stock_code = report_dict.get("stock_code", "")

        # Get yesterday's report
        yesterday_report = get_report(stock_code, yesterday)
        yesterday_data = None
        if yesterday_report:
            try:
                yesterday_data = json.loads(yesterday_report.analysis_json)
            except json.JSONDecodeError:
                logger.warning(
                    "Failed to parse yesterday report",
                    stock_code=stock_code,
                )

        # Compare reports
        incremental = compare_reports(report_dict, yesterday_data)
        incremental_reports.append(incremental)

    result.changes_detected = sum(
        1 for r in incremental_reports if r.has_significant_changes
    )

    logger.info(
        "Comparison complete",
        stocks_with_changes=result.changes_detected,
    )

    # Step 6: Format email
    email_body = format_incremental_email(
        reports=incremental_reports,
        date_str=today.isoformat(),
        failed_stocks=failed_stocks if failed_stocks else None,
    )
    email_subject = format_email_subject(incremental_reports, today.isoformat())

    if dry_run:
        # Print email content instead of sending
        print("\n" + "=" * 60)
        print(f"Subject: {email_subject}")
        print("=" * 60)
        print(email_body)
        print("=" * 60 + "\n")
        result.email_sent = False
        result.success = True
        return result

    # Step 7: Send email
    if not config.email.recipient or not config.email.sender:
        result.error = "Email not configured"
        logger.warning("Email not configured, skipping send")
        result.success = True
        return result

    try:
        email_config = EmailConfig(
            smtp_host=config.email.smtp_host,
            smtp_port=config.email.smtp_port,
            sender=config.email.sender,
            password=config.email.password,
            recipient=config.email.recipient,
        )
        sender = EmailSender(email_config)

        # Send email with retry
        email_sent = await sender.send_with_retry(
            subject=email_subject,
            body=email_body,
            html_body=None,  # Plain text for now
            stock_count=result.stocks_analyzed,
        )

        result.email_sent = email_sent
        if not email_sent:
            result.error = "Failed to send email after retries"

    except Exception as e:
        result.error = f"Email send error: {e}"
        logger.exception("Email send failed", error=str(e))

    result.success = result.stocks_analyzed > 0 or result.error is None
    return result


async def process_pending_emails() -> int:
    """Send any pending emails from previous failures.

    Returns:
        Number of emails successfully sent.
    """
    from notifier import EmailSender, EmailConfig
    from config.settings import load_config

    try:
        config = load_config()
    except Exception as e:
        logger.error("Failed to load config for pending emails", error=str(e))
        return 0

    if not config.email.recipient:
        logger.warning("No recipient configured for pending emails")
        return 0

    email_config = EmailConfig(
        smtp_host=config.email.smtp_host,
        smtp_port=config.email.smtp_port,
        sender=config.email.sender,
        password=config.email.password,
        recipient=config.email.recipient,
    )

    sender = EmailSender(email_config)
    successful, _failed = await sender.send_pending_emails()

    logger.info("Processed pending emails", successful=successful)
    return successful