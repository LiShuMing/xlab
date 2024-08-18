"""SQLAlchemy ORM models for invest module (5 tables)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class InvestDailyReport(Base):
    __tablename__ = "invest_daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(Text, nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )

    __table_args__ = (
        Index(
            "idx_invest_daily_reports_stock_date",
            stock_code,
            report_date.desc(),
        ),
        Index(
            "uq_invest_daily_reports_stock_date",
            stock_code,
            report_date,
            unique=True,
        ),
    )


class InvestStockConfig(Base):
    __tablename__ = "invest_stock_configs"

    stock_code: Mapped[str] = mapped_column(Text, primary_key=True)
    stock_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class InvestPendingEmail(Base):
    __tablename__ = "invest_pending_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (Index("idx_invest_pending_emails_retry", retry_count),)


class InvestAnalysisTask(Base):
    __tablename__ = "invest_analysis_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(Text, nullable=False)
    stock_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    priority: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "idx_invest_analysis_tasks_status",
            status,
            priority.desc(),
        ),
    )


class InvestEmailLog(Base):
    __tablename__ = "invest_email_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    stock_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("idx_invest_email_logs_sent_at", sent_at.desc()),
    )
