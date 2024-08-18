"""Async SQLAlchemy service layer for invest — replaces raw sqlite3 operations."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.invest.db_models import (
    InvestAnalysisTask,
    InvestDailyReport,
    InvestEmailLog,
    InvestPendingEmail,
    InvestStockConfig,
)

# =============================================================================
# Daily Reports
# =============================================================================


async def save_report(
    session: AsyncSession,
    stock_code: str,
    report_date: date,
    analysis_json: str,
) -> int:
    stmt = (
        insert(InvestDailyReport)
        .values(
            stock_code=stock_code,
            report_date=report_date,
            analysis_json=analysis_json,
        )
        .on_conflict_do_update(
            index_elements=["stock_code", "report_date"],
            set_={"analysis_json": analysis_json},
        )
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.inserted_primary_key[0]


async def get_report(
    session: AsyncSession,
    stock_code: str,
    report_date: date,
) -> InvestDailyReport | None:
    stmt = select(InvestDailyReport).where(
        InvestDailyReport.stock_code == stock_code,
        InvestDailyReport.report_date == report_date,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_latest_report(
    session: AsyncSession,
    stock_code: str,
) -> InvestDailyReport | None:
    stmt = (
        select(InvestDailyReport)
        .where(InvestDailyReport.stock_code == stock_code)
        .order_by(InvestDailyReport.report_date.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_reports_for_date(
    session: AsyncSession,
    report_date: date,
) -> list[InvestDailyReport]:
    stmt = select(InvestDailyReport).where(InvestDailyReport.report_date == report_date)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_all_reports(session: AsyncSession) -> int:
    result = await session.execute(delete(InvestDailyReport))
    await session.commit()
    return result.rowcount


async def delete_reports_before(
    session: AsyncSession,
    cutoff_date: date,
) -> int:
    result = await session.execute(
        delete(InvestDailyReport).where(InvestDailyReport.report_date < cutoff_date)
    )
    await session.commit()
    return result.rowcount


# =============================================================================
# Stock Configs
# =============================================================================


async def sync_stock_configs(
    session: AsyncSession,
    stocks: list[dict],
) -> int:
    if not stocks:
        return 0

    provided_codes: set[str] = set()
    count = 0

    for stock in stocks:
        code = stock.get("code")
        name = stock.get("name", "")
        if not code:
            continue
        provided_codes.add(code)

        stmt = (
            insert(InvestStockConfig)
            .values(stock_code=code, stock_name=name, is_active=True)
            .on_conflict_do_update(
                index_elements=["stock_code"],
                set_={"stock_name": name, "is_active": True},
            )
        )
        await session.execute(stmt)
        count += 1

    # Deactivate stocks not in the provided list
    existing = await session.execute(select(InvestStockConfig.stock_code))
    existing_codes = {row[0] for row in existing.fetchall()}
    codes_to_deactivate = existing_codes - provided_codes

    if codes_to_deactivate:
        await session.execute(
            update(InvestStockConfig)
            .where(InvestStockConfig.stock_code.in_(codes_to_deactivate))
            .values(is_active=False)
        )

    await session.commit()
    return count


async def get_active_stocks(
    session: AsyncSession,
) -> list[InvestStockConfig]:
    stmt = (
        select(InvestStockConfig)
        .where(InvestStockConfig.is_active.is_(True))
        .order_by(InvestStockConfig.stock_code)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


# =============================================================================
# Pending Emails
# =============================================================================


async def save_pending_email(
    session: AsyncSession,
    recipient: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    task_id: int | None = None,
) -> int:
    stmt = (
        insert(InvestPendingEmail)
        .values(
            recipient=recipient,
            subject=subject,
            body=body,
            html_body=html_body,
            task_id=task_id,
        )
        .returning(InvestPendingEmail.id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def get_pending_emails(
    session: AsyncSession,
    max_retries: int = 3,
) -> list[InvestPendingEmail]:
    stmt = (
        select(InvestPendingEmail)
        .where(InvestPendingEmail.retry_count < max_retries)
        .order_by(InvestPendingEmail.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_pending_email(
    session: AsyncSession,
    email_id: int,
) -> bool:
    result = await session.execute(delete(InvestPendingEmail).where(InvestPendingEmail.id == email_id))
    await session.commit()
    return result.rowcount > 0


async def increment_retry_count(
    session: AsyncSession,
    email_id: int,
) -> int:
    stmt = (
        update(InvestPendingEmail)
        .where(InvestPendingEmail.id == email_id)
        .values(retry_count=InvestPendingEmail.retry_count + 1)
        .returning(InvestPendingEmail.retry_count)
    )
    result = await session.execute(stmt)
    await session.commit()
    row = result.fetchone()
    return row[0] if row else 0


# =============================================================================
# Email Logs
# =============================================================================


async def log_email(
    session: AsyncSession,
    recipient: str,
    subject: str,
    stock_count: int,
    status: str,
    error_message: str | None = None,
) -> int:
    stmt = (
        insert(InvestEmailLog)
        .values(
            recipient=recipient,
            subject=subject,
            stock_count=stock_count,
            status=status,
            error_message=error_message,
        )
        .returning(InvestEmailLog.id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def get_recent_email_logs(
    session: AsyncSession,
    limit: int = 100,
) -> list[InvestEmailLog]:
    stmt = select(InvestEmailLog).order_by(InvestEmailLog.sent_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# =============================================================================
# Analysis Tasks
# =============================================================================


async def save_analysis_task(
    session: AsyncSession,
    stock_code: str,
    stock_name: str | None = None,
    priority: int = 0,
) -> int:
    stmt = (
        insert(InvestAnalysisTask)
        .values(
            stock_code=stock_code,
            stock_name=stock_name,
            priority=priority,
        )
        .returning(InvestAnalysisTask.id)
    )
    result = await session.execute(stmt)
    await session.commit()
    return result.scalar_one()


async def get_pending_tasks(
    session: AsyncSession,
    limit: int = 10,
) -> list[InvestAnalysisTask]:
    stmt = (
        select(InvestAnalysisTask)
        .where(InvestAnalysisTask.status == "pending")
        .order_by(
            InvestAnalysisTask.priority.desc(),
            InvestAnalysisTask.created_at.asc(),
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def update_task_status(
    session: AsyncSession,
    task_id: int,
    status: str,
    error_message: str | None = None,
) -> bool:
    values: dict = {"status": status}
    now = datetime.now(UTC)

    if status == "running":
        values["started_at"] = now
    elif status in ("completed", "failed"):
        values["completed_at"] = now
        values["error_message"] = error_message

    result = await session.execute(
        update(InvestAnalysisTask).where(InvestAnalysisTask.id == task_id).values(**values)
    )
    await session.commit()
    return result.rowcount > 0


async def get_task_by_id(
    session: AsyncSession,
    task_id: int,
) -> InvestAnalysisTask | None:
    stmt = select(InvestAnalysisTask).where(InvestAnalysisTask.id == task_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def cleanup_completed_tasks(
    session: AsyncSession,
    days: int = 7,
) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await session.execute(
        delete(InvestAnalysisTask).where(
            InvestAnalysisTask.status.in_(["completed", "failed"]),
            InvestAnalysisTask.completed_at < cutoff,
        )
    )
    await session.commit()
    return result.rowcount
