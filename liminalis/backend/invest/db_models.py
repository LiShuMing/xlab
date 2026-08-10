"""SQLAlchemy ORM models for invest module (5 tables)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class InvestDailyReport(Base):
    __tablename__ = "invest_daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(Text, nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    analysis_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class InvestPendingEmail(Base):
    __tablename__ = "invest_pending_emails"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    recipient: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    stock_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_invest_email_logs_sent_at", sent_at.desc()),)


class InvestThesis(Base):
    __tablename__ = "invest_theses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(Text, nullable=False)
    stock_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'watchlist'"))
    core_thesis: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    supporting_evidence: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    counter_evidence: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    disconfirming_signals: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    margin_of_safety: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    expected_holding_period: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    confidence: Mapped[str] = mapped_column(Text, nullable=False, server_default="medium")
    source_report_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invest_daily_reports.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("uq_invest_theses_stock_code", stock_code, unique=True),
        Index("idx_invest_theses_status", status),
    )


class InvestWatchItem(Base):
    __tablename__ = "invest_watch_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(Text, nullable=False)
    thesis_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invest_theses.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default="manual")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("idx_invest_watch_items_stock_status", stock_code, status),
        Index("idx_invest_watch_items_thesis", thesis_id),
    )


class InvestJournalEntry(Base):
    __tablename__ = "invest_journal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(Text, nullable=False)
    thesis_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invest_theses.id", ondelete="SET NULL"), nullable=True
    )
    entry_type: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    emotion: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    review_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    __table_args__ = (
        Index("idx_invest_journal_stock_created", stock_code, created_at.desc()),
        Index("idx_invest_journal_thesis", thesis_id),
    )


class InvestReview(Base):
    __tablename__ = "invest_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stock_code: Mapped[str] = mapped_column(Text, nullable=False)
    thesis_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("invest_theses.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(Text, nullable=False, server_default="no_action")
    thesis_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    evidence_update: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    valuation_update: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    discipline_notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    next_action: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    __table_args__ = (
        Index("idx_invest_reviews_stock_created", stock_code, created_at.desc()),
        Index("idx_invest_reviews_thesis", thesis_id),
    )
