"""invest initial schema: 5 tables for daily_reports, stock_configs,
pending_emails, analysis_tasks, email_logs

Revision ID: 0002_invest_initial
Revises: 0001_initial
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_invest_initial"
down_revision: str | None = "0001_initial"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invest_daily_reports",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("stock_code", sa.Text(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("analysis_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_invest_daily_reports_stock_date",
        "invest_daily_reports",
        ["stock_code", sa.text("report_date DESC")],
    )
    op.create_index(
        "uq_invest_daily_reports_stock_date",
        "invest_daily_reports",
        ["stock_code", "report_date"],
        unique=True,
    )

    op.create_table(
        "invest_stock_configs",
        sa.Column("stock_code", sa.Text(), primary_key=True),
        sa.Column("stock_name", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "invest_pending_emails",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "idx_invest_pending_emails_retry",
        "invest_pending_emails",
        ["retry_count"],
    )

    op.create_table(
        "invest_analysis_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("stock_code", sa.Text(), nullable=False),
        sa.Column("stock_name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'")),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_invest_analysis_tasks_status",
        "invest_analysis_tasks",
        ["status", sa.text("priority DESC")],
    )

    op.create_table(
        "invest_email_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
        ),
        sa.Column("recipient", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("stock_count", sa.Integer(), server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index(
        "idx_invest_email_logs_sent_at",
        "invest_email_logs",
        [sa.text("sent_at DESC")],
    )


def downgrade() -> None:
    op.drop_table("invest_email_logs")
    op.drop_table("invest_analysis_tasks")
    op.drop_table("invest_pending_emails")
    op.drop_table("invest_stock_configs")
    op.drop_table("invest_daily_reports")
