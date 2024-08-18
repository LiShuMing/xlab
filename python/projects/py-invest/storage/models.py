"""SQLite models and database initialization."""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from core.logger import get_logger

logger = get_logger("storage.models")


def get_db_path() -> Path:
    """Get database file path.

    Returns:
        Path to the SQLite database file at ~/.py-invest/data.db
    """
    db_dir = Path.home() / ".py-invest"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "data.db"


def init_db() -> None:
    """Initialize database tables if they don't exist."""
    db_path = get_db_path()
    logger.info("Initializing database", db_path=str(db_path))

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Daily reports table - stores analysis reports by stock and date
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                report_date DATE NOT NULL,
                analysis_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_code, report_date)
            )
        """)

        # Stock configurations table - tracks active stocks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_configs (
                stock_code TEXT PRIMARY KEY,
                stock_name TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Pending emails queue - for retry on failed sends
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pending_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                body TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                html_body TEXT,
                task_id INTEGER
            )
        """)

        # Analysis tasks table - for background processing
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                status TEXT DEFAULT 'pending',
                priority INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT
            )
        """)

        # Email logs for debugging and monitoring
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                stock_count INTEGER DEFAULT 0,
                status TEXT NOT NULL,
                error_message TEXT
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_daily_reports_stock_date
            ON daily_reports(stock_code, report_date DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pending_emails_retry
            ON pending_emails(retry_count)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_email_logs_sent_at
            ON email_logs(sent_at DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_analysis_tasks_status
            ON analysis_tasks(status, priority DESC)
        """)

        # Migration: Add html_body and task_id columns to pending_emails if they don't exist
        cursor.execute("PRAGMA table_info(pending_emails)")
        columns = {row[1] for row in cursor.fetchall()}
        if "html_body" not in columns:
            cursor.execute("ALTER TABLE pending_emails ADD COLUMN html_body TEXT")
            logger.info("Added html_body column to pending_emails")
        if "task_id" not in columns:
            cursor.execute("ALTER TABLE pending_emails ADD COLUMN task_id INTEGER")
            logger.info("Added task_id column to pending_emails")

        conn.commit()
        logger.info("Database initialized successfully")

    except sqlite3.OperationalError as e:
        logger.error("Failed to initialize database", error=str(e))
        raise
    finally:
        conn.close()


@dataclass
class DailyReport:
    """Daily analysis report record."""

    id: Optional[int]
    stock_code: str
    report_date: date
    analysis_json: str
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: tuple) -> "DailyReport":
        """Create DailyReport from database row.

        Args:
            row: Tuple from database query (id, stock_code, report_date, analysis_json, created_at)

        Returns:
            DailyReport instance
        """
        return cls(
            id=row[0],
            stock_code=row[1],
            report_date=date.fromisoformat(row[2]) if isinstance(row[2], str) else row[2],
            analysis_json=row[3],
            created_at=datetime.fromisoformat(row[4]) if row[4] and isinstance(row[4], str) else row[4],
        )


@dataclass
class StockConfig:
    """Stock configuration record."""

    stock_code: str
    stock_name: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: tuple) -> "StockConfig":
        """Create StockConfig from database row.

        Args:
            row: Tuple from database query (stock_code, stock_name, is_active, created_at)

        Returns:
            StockConfig instance
        """
        return cls(
            stock_code=row[0],
            stock_name=row[1],
            is_active=bool(row[2]) if row[2] is not None else True,
            created_at=datetime.fromisoformat(row[3]) if row[3] and isinstance(row[3], str) else row[3],
        )


@dataclass
class PendingEmail:
    """Pending email in retry queue."""

    id: Optional[int]
    created_at: Optional[datetime]
    recipient: str
    subject: str
    body: str
    retry_count: int = 0
    html_body: Optional[str] = None
    task_id: Optional[int] = None

    @classmethod
    def from_row(cls, row: tuple) -> "PendingEmail":
        """Create PendingEmail from database row.

        Args:
            row: Tuple from database query (id, created_at, recipient, subject, body, retry_count, html_body, task_id)

        Returns:
            PendingEmail instance
        """
        # Handle both old schema (6 columns) and new schema (8 columns)
        if len(row) >= 8:
            return cls(
                id=row[0],
                created_at=datetime.fromisoformat(row[1]) if row[1] and isinstance(row[1], str) else row[1],
                recipient=row[2],
                subject=row[3],
                body=row[4],
                retry_count=row[5] if row[5] is not None else 0,
                html_body=row[6],
                task_id=row[7],
            )
        else:
            # Legacy format (6 columns)
            return cls(
                id=row[0],
                created_at=datetime.fromisoformat(row[1]) if row[1] and isinstance(row[1], str) else row[1],
                recipient=row[2],
                subject=row[3],
                body=row[4],
                retry_count=row[5] if row[5] is not None else 0,
            )


@dataclass
class EmailLog:
    """Email log record."""

    id: Optional[int]
    sent_at: Optional[datetime]
    recipient: str
    subject: str
    stock_count: int
    status: str
    error_message: Optional[str] = None

    @classmethod
    def from_row(cls, row: tuple) -> "EmailLog":
        """Create EmailLog from database row.

        Args:
            row: Tuple from database query (id, sent_at, recipient, subject, stock_count, status, error_message)

        Returns:
            EmailLog instance
        """
        return cls(
            id=row[0],
            sent_at=datetime.fromisoformat(row[1]) if row[1] and isinstance(row[1], str) else row[1],
            recipient=row[2],
            subject=row[3],
            stock_count=row[4] if row[4] is not None else 0,
            status=row[5],
            error_message=row[6],
        )


@dataclass
class AnalysisTask:
    """Analysis task for background processing.

    Attributes:
        id: Task ID (auto-generated).
        stock_code: Stock ticker symbol.
        stock_name: Stock display name.
        status: Task status (pending, running, completed, failed).
        priority: Task priority (higher = more urgent).
        created_at: Task creation timestamp.
        started_at: Task start timestamp.
        completed_at: Task completion timestamp.
        error_message: Error message if failed.
    """

    id: Optional[int]
    stock_code: str
    stock_name: Optional[str] = None
    status: str = "pending"
    priority: int = 0
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    @classmethod
    def from_row(cls, row: tuple) -> "AnalysisTask":
        """Create AnalysisTask from database row.

        Args:
            row: Tuple from database query.

        Returns:
            AnalysisTask instance
        """
        return cls(
            id=row[0],
            stock_code=row[1],
            stock_name=row[2],
            status=row[3] if row[3] else "pending",
            priority=row[4] if row[4] is not None else 0,
            created_at=datetime.fromisoformat(row[5]) if row[5] and isinstance(row[5], str) else row[5],
            started_at=datetime.fromisoformat(row[6]) if row[6] and isinstance(row[6], str) else row[6],
            completed_at=datetime.fromisoformat(row[7]) if row[7] and isinstance(row[7], str) else row[7],
            error_message=row[8],
        )