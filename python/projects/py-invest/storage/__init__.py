"""Storage layer initialization."""

from storage.models import (
    DailyReport,
    EmailLog,
    PendingEmail,
    StockConfig,
    get_db_path,
    init_db,
)
from storage.repository import (
    delete_pending_email,
    get_latest_report,
    get_pending_emails,
    get_report,
    increment_retry_count,
    log_email,
    save_pending_email,
    save_report,
    sync_stock_configs,
)

__all__ = [
    # Models
    "DailyReport",
    "StockConfig",
    "PendingEmail",
    "EmailLog",
    "get_db_path",
    "init_db",
    # Repository
    "save_report",
    "get_report",
    "get_latest_report",
    "save_pending_email",
    "get_pending_emails",
    "delete_pending_email",
    "increment_retry_count",
    "log_email",
    "sync_stock_configs",
]