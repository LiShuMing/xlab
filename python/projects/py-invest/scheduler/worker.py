"""Background worker for processing analysis tasks.

This module provides the AnalysisWorker class that:
1. Fetches pending tasks from the database
2. Runs analysis for each stock
3. Saves results to daily_reports
4. Creates email tasks for completed analyses
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from core.logger import get_logger
from storage import (
    init_db,
    get_pending_tasks,
    update_task_status,
    save_report,
    save_pending_email,
    AnalysisTask,
)

logger = get_logger("scheduler.worker")

# Timeout for single stock analysis (seconds)
TASK_TIMEOUT = 300


@dataclass
class WorkerResult:
    """Result of processing a single task.

    Attributes:
        task_id: Task ID.
        stock_code: Stock code analyzed.
        success: Whether analysis succeeded.
        error: Error message if failed.
        duration: Time taken in seconds.
    """

    task_id: int
    stock_code: str
    success: bool
    error: Optional[str] = None
    duration: float = 0.0


class AnalysisWorker:
    """Background worker for processing analysis tasks.

    Fetches tasks from the database, runs analysis, and saves results.
    Supports both one-shot and continuous operation modes.
    """

    def __init__(self, lang: str = "zh"):
        """Initialize the worker.

        Args:
            lang: Output language for reports ("zh" or "en").
        """
        self.lang = lang
        self._running = False

    async def process_task(self, task: AnalysisTask) -> WorkerResult:
        """Process a single analysis task.

        Args:
            task: AnalysisTask to process.

        Returns:
            WorkerResult with outcome.
        """
        from agents.orchestrator import SimpleAgentOrchestrator

        start_time = time.time()
        task_id = task.id or 0
        stock_code = task.stock_code

        logger.info(
            "Processing task",
            task_id=task_id,
            stock_code=stock_code,
        )

        # Mark task as running
        update_task_status(task_id, "running")

        try:
            # Run analysis
            orchestrator = SimpleAgentOrchestrator(lang=self.lang)
            state = await asyncio.wait_for(
                orchestrator.analyze(stock_code, "daily_summary"),
                timeout=TASK_TIMEOUT,
            )

            duration = time.time() - start_time

            if state.error:
                # Analysis failed
                update_task_status(task_id, "failed", error_message=state.error)
                return WorkerResult(
                    task_id=task_id,
                    stock_code=stock_code,
                    success=False,
                    error=state.error,
                    duration=duration,
                )

            if not state.report:
                # No report generated
                error = "No report generated"
                update_task_status(task_id, "failed", error_message=error)
                return WorkerResult(
                    task_id=task_id,
                    stock_code=stock_code,
                    success=False,
                    error=error,
                    duration=duration,
                )

            # Success - save report
            await self._save_report_and_create_email(task, state.report)

            update_task_status(task_id, "completed")
            logger.info(
                "Task completed",
                task_id=task_id,
                stock_code=stock_code,
                duration=duration,
                rating=state.report.rating,
            )

            return WorkerResult(
                task_id=task_id,
                stock_code=stock_code,
                success=True,
                duration=duration,
            )

        except asyncio.TimeoutError:
            duration = time.time() - start_time
            error = f"Analysis timed out after {TASK_TIMEOUT}s"
            update_task_status(task_id, "failed", error_message=error)
            logger.error("Task timeout", task_id=task_id, stock_code=stock_code)
            return WorkerResult(
                task_id=task_id,
                stock_code=stock_code,
                success=False,
                error=error,
                duration=duration,
            )

        except Exception as e:
            duration = time.time() - start_time
            error = str(e)
            update_task_status(task_id, "failed", error_message=error)
            logger.exception(
                "Task failed with exception",
                task_id=task_id,
                stock_code=stock_code,
                error=error,
            )
            return WorkerResult(
                task_id=task_id,
                stock_code=stock_code,
                success=False,
                error=error,
                duration=duration,
            )

    async def _save_report_and_create_email(
        self,
        task: AnalysisTask,
        report: Any,
    ) -> None:
        """Save report to database and create email task.

        Args:
            task: The analysis task.
            report: The generated Report object.
        """
        from modules.report_generator.formatter import ReportFormatter, ReportFormat
        from notifier.email_templates import format_stock_report_html
        from config.settings import load_config

        # Convert report to dict
        report_dict = json.loads(
            ReportFormatter.format(report, ReportFormat.JSON)
        )
        report_dict["stock_name"] = task.stock_name or report.stock_name

        # Save to daily_reports
        today = date.today()
        save_report(
            stock_code=task.stock_code,
            report_date=today,
            analysis_json=json.dumps(report_dict, ensure_ascii=False),
        )

        # Generate HTML email content
        html_body = format_stock_report_html(report, self.lang)

        # Get recipient from config
        recipient = ""
        try:
            config = load_config()
            recipient = config.email.recipient or ""
        except Exception:
            pass

        # Create email task (pending_email record)
        save_pending_email(
            recipient=recipient,
            subject=f"[{task.stock_code}] {report.stock_name} - Daily Analysis {today}",
            body=ReportFormatter.format(report, ReportFormat.MARKDOWN, lang=self.lang),
            html_body=html_body,
            task_id=task.id,
        )

    async def run_once(self, max_tasks: int = 10) -> list[WorkerResult]:
        """Run worker once, processing available tasks.

        Args:
            max_tasks: Maximum number of tasks to process in one run.

        Returns:
            List of WorkerResult for each processed task.
        """
        init_db()

        tasks = get_pending_tasks(limit=max_tasks)
        if not tasks:
            logger.info("No pending tasks")
            return []

        logger.info("Processing tasks", count=len(tasks))

        results = []
        for task in tasks:
            result = await self.process_task(task)
            results.append(result)

            # Small delay between tasks to avoid rate limiting
            await asyncio.sleep(1)

        return results

    async def run_forever(self, poll_interval: int = 60) -> None:
        """Run worker continuously, polling for new tasks.

        Args:
            poll_interval: Seconds to wait between polls.
        """
        self._running = True
        logger.info("Starting worker", poll_interval=poll_interval)

        while self._running:
            try:
                results = await self.run_once()

                # Log summary
                if results:
                    successful = sum(1 for r in results if r.success)
                    failed = len(results) - successful
                    logger.info(
                        "Batch complete",
                        total=len(results),
                        successful=successful,
                        failed=failed,
                    )

            except Exception as e:
                logger.exception("Worker error", error=str(e))

            # Wait before next poll
            await asyncio.sleep(poll_interval)

    def stop(self) -> None:
        """Stop the worker."""
        self._running = False
        logger.info("Worker stopped")


async def run_worker(once: bool = True, max_tasks: int = 10) -> list[WorkerResult]:
    """Convenience function to run the worker.

    Args:
        once: If True, run once; if False, run forever.
        max_tasks: Maximum tasks per run (for once mode).

    Returns:
        List of WorkerResult (empty for forever mode).
    """
    worker = AnalysisWorker()

    if once:
        return await worker.run_once(max_tasks=max_tasks)
    else:
        await worker.run_forever()
        return []