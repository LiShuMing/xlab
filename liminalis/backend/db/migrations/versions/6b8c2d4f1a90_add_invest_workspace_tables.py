"""add invest workspace tables

Revision ID: 6b8c2d4f1a90
Revises: 5d2f8a7c1b0e
Create Date: 2026-06-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6b8c2d4f1a90"
down_revision: str | Sequence[str] | None = "5d2f8a7c1b0e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invest_theses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_code", sa.Text(), nullable=False),
        sa.Column("stock_name", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'watchlist'"), nullable=False),
        sa.Column("core_thesis", sa.Text(), server_default="", nullable=False),
        sa.Column("supporting_evidence", sa.dialects.postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("counter_evidence", sa.dialects.postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column(
            "disconfirming_signals",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("margin_of_safety", sa.Text(), server_default="", nullable=False),
        sa.Column("expected_holding_period", sa.Text(), server_default="", nullable=False),
        sa.Column("confidence", sa.Text(), server_default="medium", nullable=False),
        sa.Column("source_report_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_report_id"], ["invest_daily_reports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_invest_theses_stock_code", "invest_theses", ["stock_code"], unique=True)
    op.create_index("idx_invest_theses_status", "invest_theses", ["status"], unique=False)

    op.create_table(
        "invest_watch_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_code", sa.Text(), nullable=False),
        sa.Column("thesis_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.Text(), server_default="manual", nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("condition", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["thesis_id"], ["invest_theses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_invest_watch_items_stock_status",
        "invest_watch_items",
        ["stock_code", "status"],
        unique=False,
    )
    op.create_index("idx_invest_watch_items_thesis", "invest_watch_items", ["thesis_id"], unique=False)

    op.create_table(
        "invest_journal_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_code", sa.Text(), nullable=False),
        sa.Column("thesis_id", sa.Integer(), nullable=True),
        sa.Column("entry_type", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), server_default="", nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), server_default="", nullable=False),
        sa.Column("emotion", sa.Text(), server_default="", nullable=False),
        sa.Column("meta", sa.dialects.postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("review_at", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["thesis_id"], ["invest_theses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_invest_journal_stock_created",
        "invest_journal_entries",
        ["stock_code", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index("idx_invest_journal_thesis", "invest_journal_entries", ["thesis_id"], unique=False)

    op.create_table(
        "invest_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_code", sa.Text(), nullable=False),
        sa.Column("thesis_id", sa.Integer(), nullable=True),
        sa.Column("decision", sa.Text(), server_default="no_action", nullable=False),
        sa.Column("thesis_valid", sa.Boolean(), nullable=True),
        sa.Column("evidence_update", sa.Text(), server_default="", nullable=False),
        sa.Column("valuation_update", sa.Text(), server_default="", nullable=False),
        sa.Column("discipline_notes", sa.Text(), server_default="", nullable=False),
        sa.Column("next_action", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["thesis_id"], ["invest_theses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_invest_reviews_stock_created",
        "invest_reviews",
        ["stock_code", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index("idx_invest_reviews_thesis", "invest_reviews", ["thesis_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_invest_reviews_thesis", table_name="invest_reviews")
    op.drop_index("idx_invest_reviews_stock_created", table_name="invest_reviews")
    op.drop_table("invest_reviews")

    op.drop_index("idx_invest_journal_thesis", table_name="invest_journal_entries")
    op.drop_index("idx_invest_journal_stock_created", table_name="invest_journal_entries")
    op.drop_table("invest_journal_entries")

    op.drop_index("idx_invest_watch_items_thesis", table_name="invest_watch_items")
    op.drop_index("idx_invest_watch_items_stock_status", table_name="invest_watch_items")
    op.drop_table("invest_watch_items")

    op.drop_index("idx_invest_theses_status", table_name="invest_theses")
    op.drop_index("uq_invest_theses_stock_code", table_name="invest_theses")
    op.drop_table("invest_theses")
