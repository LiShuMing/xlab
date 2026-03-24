"""Repository layer for database CRUD operations."""

import sqlite3
from datetime import date, datetime
from typing import Optional

from core.logger import get_logger
from storage.models import (
    DailyReport,
    EmailLog,
    PendingEmail,
    StockConfig,
    get_db_path,
    init_db,
)

logger = get_logger("storage.repository")


def _get_connection() -> sqlite3.Connection:
    """Get database connection.

    Returns:
        SQLite connection with row factory enabled.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


# =============================================================================
# Daily Reports CRUD
# =============================================================================


def save_report(stock_code: str, report_date: date, analysis_json: str) -> int:
    """Save or update a daily analysis report.

    Args:
        stock_code: Stock code (e.g., 'sh600519').
        report_date: Date of the report.
        analysis_json: JSON string containing the full analysis.

    Returns:
        The row ID of the inserted/updated record.

    Raises:
        sqlite3.OperationalError: If database write fails.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO daily_reports (stock_code, report_date, analysis_json)
            VALUES (?, ?, ?)
            ON CONFLICT(stock_code, report_date)
            DO UPDATE SET analysis_json = excluded.analysis_json
            """,
            (stock_code, report_date.isoformat(), analysis_json),
        )
        conn.commit()
        row_id = cursor.lastrowid
        logger.info(
            "Saved daily report",
            stock_code=stock_code,
            report_date=str(report_date),
            row_id=row_id,
        )
        return row_id

    except sqlite3.OperationalError as e:
        logger.error(
            "Failed to save report",
            stock_code=stock_code,
            report_date=str(report_date),
            error=str(e),
        )
        raise
    finally:
        conn.close()


def get_report(stock_code: str, report_date: date) -> Optional[DailyReport]:
    """Get a specific daily report.

    Args:
        stock_code: Stock code.
        report_date: Report date.

    Returns:
        DailyReport if found, None otherwise.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, stock_code, report_date, analysis_json, created_at
            FROM daily_reports
            WHERE stock_code = ? AND report_date = ?
            """,
            (stock_code, report_date.isoformat()),
        )
        row = cursor.fetchone()
        if row:
            return DailyReport.from_row(tuple(row))
        return None

    finally:
        conn.close()


def get_latest_report(stock_code: str) -> Optional[DailyReport]:
    """Get the most recent report for a stock.

    Args:
        stock_code: Stock code.

    Returns:
        DailyReport if found, None otherwise.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, stock_code, report_date, analysis_json, created_at
            FROM daily_reports
            WHERE stock_code = ?
            ORDER BY report_date DESC
            LIMIT 1
            """,
            (stock_code,),
        )
        row = cursor.fetchone()
        if row:
            return DailyReport.from_row(tuple(row))
        return None

    finally:
        conn.close()


def get_reports_for_date(report_date: date) -> list[DailyReport]:
    """Get all reports for a specific date.

    Args:
        report_date: Report date.

    Returns:
        List of DailyReport objects.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, stock_code, report_date, analysis_json, created_at
            FROM daily_reports
            WHERE report_date = ?
            """,
            (report_date.isoformat(),),
        )
        rows = cursor.fetchall()
        return [DailyReport.from_row(tuple(row)) for row in rows]

    finally:
        conn.close()


# =============================================================================
# Stock Configs CRUD
# =============================================================================


def sync_stock_configs(stocks: list[dict]) -> int:
    """Sync stock configurations from config file.

    Updates existing stocks and adds new ones. Does not delete stocks that are
    not in the provided list (only marks them as inactive).

    Args:
        stocks: List of stock dicts with 'code' and 'name' keys.

    Returns:
        Number of stocks synced.

    Raises:
        sqlite3.OperationalError: If database write fails.
    """
    if not stocks:
        logger.info("No stocks to sync")
        return 0

    conn = _get_connection()
    cursor = conn.cursor()

    try:
        # Get existing stock codes
        cursor.execute("SELECT stock_code FROM stock_configs")
        existing_codes = {row[0] for row in cursor.fetchall()}

        provided_codes = set()
        count = 0

        for stock in stocks:
            code = stock.get("code")
            name = stock.get("name", "")
            if not code:
                continue

            provided_codes.add(code)

            if code in existing_codes:
                # Update existing stock
                cursor.execute(
                    """
                    UPDATE stock_configs
                    SET stock_name = ?, is_active = TRUE
                    WHERE stock_code = ?
                    """,
                    (name, code),
                )
            else:
                # Insert new stock
                cursor.execute(
                    """
                    INSERT INTO stock_configs (stock_code, stock_name, is_active)
                    VALUES (?, ?, TRUE)
                    """,
                    (code, name),
                )
            count += 1

        # Mark stocks not in the list as inactive
        codes_to_deactivate = existing_codes - provided_codes
        if codes_to_deactivate:
            placeholders = ",".join("?" * len(codes_to_deactivate))
            cursor.execute(
                f"""
                UPDATE stock_configs
                SET is_active = FALSE
                WHERE stock_code IN ({placeholders})
                """,
                list(codes_to_deactivate),
            )
            logger.info(
                "Deactivated stocks",
                codes=list(codes_to_deactivate),
            )

        conn.commit()
        logger.info("Synced stock configs", count=count)
        return count

    except sqlite3.OperationalError as e:
        logger.error("Failed to sync stock configs", error=str(e))
        raise
    finally:
        conn.close()


def get_active_stocks() -> list[StockConfig]:
    """Get all active stock configurations.

    Returns:
        List of active StockConfig objects.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT stock_code, stock_name, is_active, created_at
            FROM stock_configs
            WHERE is_active = TRUE
            ORDER BY stock_code
            """
        )
        rows = cursor.fetchall()
        return [StockConfig.from_row(tuple(row)) for row in rows]

    finally:
        conn.close()


# =============================================================================
# Pending Emails CRUD
# =============================================================================


def save_pending_email(recipient: str, subject: str, body: str) -> int:
    """Add an email to the pending queue.

    Args:
        recipient: Email recipient address.
        subject: Email subject.
        body: Email body content.

    Returns:
        The row ID of the inserted record.

    Raises:
        sqlite3.OperationalError: If database write fails.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO pending_emails (recipient, subject, body)
            VALUES (?, ?, ?)
            """,
            (recipient, subject, body),
        )
        conn.commit()
        row_id = cursor.lastrowid
        logger.info(
            "Saved pending email",
            recipient=recipient,
            subject=subject,
            row_id=row_id,
        )
        return row_id

    except sqlite3.OperationalError as e:
        logger.error(
            "Failed to save pending email",
            recipient=recipient,
            error=str(e),
        )
        raise
    finally:
        conn.close()


def get_pending_emails(max_retries: int = 3) -> list[PendingEmail]:
    """Get all pending emails that haven't exceeded max retries.

    Args:
        max_retries: Maximum number of retries allowed.

    Returns:
        List of PendingEmail objects.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, created_at, recipient, subject, body, retry_count
            FROM pending_emails
            WHERE retry_count < ?
            ORDER BY created_at ASC
            """,
            (max_retries,),
        )
        rows = cursor.fetchall()
        return [PendingEmail.from_row(tuple(row)) for row in rows]

    finally:
        conn.close()


def delete_pending_email(email_id: int) -> bool:
    """Delete a pending email from the queue.

    Args:
        email_id: ID of the pending email to delete.

    Returns:
        True if deleted, False if not found.

    Raises:
        sqlite3.OperationalError: If database write fails.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM pending_emails WHERE id = ?",
            (email_id,),
        )
        deleted = cursor.rowcount > 0
        conn.commit()
        if deleted:
            logger.info("Deleted pending email", email_id=email_id)
        return deleted

    except sqlite3.OperationalError as e:
        logger.error(
            "Failed to delete pending email",
            email_id=email_id,
            error=str(e),
        )
        raise
    finally:
        conn.close()


def increment_retry_count(email_id: int) -> int:
    """Increment the retry count for a pending email.

    Args:
        email_id: ID of the pending email.

    Returns:
        The new retry count.

    Raises:
        sqlite3.OperationalError: If database write fails.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE pending_emails
            SET retry_count = retry_count + 1
            WHERE id = ?
            RETURNING retry_count
            """,
            (email_id,),
        )
        row = cursor.fetchone()
        conn.commit()
        new_count = row[0] if row else 0
        logger.info(
            "Incremented retry count",
            email_id=email_id,
            new_count=new_count,
        )
        return new_count

    except sqlite3.OperationalError as e:
        logger.error(
            "Failed to increment retry count",
            email_id=email_id,
            error=str(e),
        )
        raise
    finally:
        conn.close()


# =============================================================================
# Email Logs CRUD
# =============================================================================


def log_email(
    recipient: str,
    subject: str,
    stock_count: int,
    status: str,
    error_message: Optional[str] = None,
) -> int:
    """Log an email send attempt.

    Args:
        recipient: Email recipient address.
        subject: Email subject.
        stock_count: Number of stocks in the email.
        status: Status of the send ('success' or 'failed').
        error_message: Error message if failed.

    Returns:
        The row ID of the inserted record.

    Raises:
        sqlite3.OperationalError: If database write fails.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO email_logs (recipient, subject, stock_count, status, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (recipient, subject, stock_count, status, error_message),
        )
        conn.commit()
        row_id = cursor.lastrowid
        logger.info(
            "Logged email",
            recipient=recipient,
            status=status,
            row_id=row_id,
        )
        return row_id

    except sqlite3.OperationalError as e:
        logger.error(
            "Failed to log email",
            recipient=recipient,
            error=str(e),
        )
        raise
    finally:
        conn.close()


def get_recent_email_logs(limit: int = 100) -> list[EmailLog]:
    """Get recent email logs.

    Args:
        limit: Maximum number of logs to return.

    Returns:
        List of EmailLog objects.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT id, sent_at, recipient, subject, stock_count, status, error_message
            FROM email_logs
            ORDER BY sent_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        return [EmailLog.from_row(tuple(row)) for row in rows]

    finally:
        conn.close()