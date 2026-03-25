"""Storage layer initialization."""

from storage.models import (
    AnalysisTask,
    DailyReport,
    EmailLog,
    PendingEmail,
    StockConfig,
    get_db_path,
    init_db,
)
from storage.repository import (
    cleanup_completed_tasks,
    delete_all_reports,
    delete_pending_email,
    delete_reports_before,
    get_active_stocks,
    get_latest_report,
    get_pending_emails,
    get_pending_tasks,
    get_recent_email_logs,
    get_report,
    get_task_by_id,
    increment_retry_count,
    log_email,
    save_analysis_task,
    save_pending_email,
    save_report,
    sync_stock_configs,
    update_task_status,
)

__all__ = [
    # Models
    "DailyReport",
    "StockConfig",
    "PendingEmail",
    "EmailLog",
    "AnalysisTask",
    "get_db_path",
    "init_db",
    # Repository
    "save_report",
    "get_report",
    "get_latest_report",
    "delete_all_reports",
    "delete_reports_before",
    "get_active_stocks",
    "save_pending_email",
    "get_pending_emails",
    "delete_pending_email",
    "increment_retry_count",
    "log_email",
    "sync_stock_configs",
    "get_recent_email_logs",
    # Analysis Tasks
    "save_analysis_task",
    "get_pending_tasks",
    "update_task_status",
    "get_task_by_id",
    "cleanup_completed_tasks",
]