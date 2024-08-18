"""initial schema: pgvector extension + radar tables

Captures the SCHEMA_SQL that backend/db/postgres.py:init_schema used to apply
on every connect. Future M1 migrations replace this hand-written SQL with
ORM-aware revisions.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "radar_items",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("title", sa.Text(), nullable=False, server_default=""),
        sa.Column("original_title", sa.Text(), nullable=False, server_default=""),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("product", sa.Text(), nullable=False, server_default=""),
        sa.Column("content_type", sa.Text(), nullable=False, server_default="blog"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags", sa.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("sources", sa.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("raw_content", sa.Text(), nullable=False, server_default=""),
        sa.Column("sync_batch", sa.Date(), nullable=True),
    )
    op.create_index(
        "idx_radar_items_sync_batch",
        "radar_items",
        [
            sa.text("sync_batch DESC NULLS LAST"),
            sa.text("published_date DESC NULLS LAST"),
            sa.text("fetched_at DESC"),
        ],
    )
    op.create_index("idx_radar_items_product", "radar_items", ["product"])
    op.create_index("idx_radar_items_content_type", "radar_items", ["content_type"])
    op.create_index(
        "idx_radar_items_published_date",
        "radar_items",
        [sa.text("published_date DESC NULLS LAST")],
    )
    op.create_index(
        "idx_radar_items_tags",
        "radar_items",
        ["tags"],
        postgresql_using="gin",
    )

    op.create_table(
        "radar_ingestion_jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "item_id",
            sa.Text(),
            sa.ForeignKey("radar_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("submitted_by", sa.Text(), nullable=True),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("idx_radar_ingestion_jobs_status", "radar_ingestion_jobs", ["status"])
    op.create_index(
        "idx_radar_ingestion_jobs_submitted_at",
        "radar_ingestion_jobs",
        [sa.text("submitted_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_radar_ingestion_jobs_submitted_at", table_name="radar_ingestion_jobs")
    op.drop_index("idx_radar_ingestion_jobs_status", table_name="radar_ingestion_jobs")
    op.drop_table("radar_ingestion_jobs")

    op.drop_index("idx_radar_items_tags", table_name="radar_items")
    op.drop_index("idx_radar_items_published_date", table_name="radar_items")
    op.drop_index("idx_radar_items_content_type", table_name="radar_items")
    op.drop_index("idx_radar_items_product", table_name="radar_items")
    op.drop_index("idx_radar_items_sync_batch", table_name="radar_items")
    op.drop_table("radar_items")

    # vector extension is intentionally NOT dropped here; other databases
    # in the cluster may rely on it.
