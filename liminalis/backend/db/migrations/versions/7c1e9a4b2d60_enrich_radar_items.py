"""Add structured Radar enrichment, ranking, provenance, and search index.

Revision ID: 7c1e9a4b2d60
Revises: 6b8c2d4f1a90
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c1e9a4b2d60"
down_revision: str | Sequence[str] | None = "6b8c2d4f1a90"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("radar_items", sa.Column("channel", sa.Text(), nullable=False, server_default="web"))
    op.add_column("radar_items", sa.Column("source_id", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "radar_items", sa.Column("authority", sa.Text(), nullable=False, server_default="community")
    )
    op.add_column("radar_items", sa.Column("author", sa.Text(), nullable=True))
    op.add_column("radar_items", sa.Column("version", sa.Text(), nullable=True))
    op.add_column(
        "radar_items", sa.Column("components", sa.ARRAY(sa.Text()), nullable=False, server_default="{}")
    )
    op.add_column("radar_items", sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"))
    op.add_column("radar_items", sa.Column("confidence", sa.Float(), nullable=False, server_default="0"))
    op.add_column("radar_items", sa.Column("score", sa.Float(), nullable=False, server_default="0"))
    op.add_column("radar_items", sa.Column("rank", sa.Integer(), nullable=True))
    op.add_column(
        "radar_items", sa.Column("rank_reasons", sa.ARRAY(sa.Text()), nullable=False, server_default="{}")
    )
    op.add_column("radar_items", sa.Column("content_hash", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "radar_items",
        sa.Column("analysis_provider", sa.Text(), nullable=False, server_default="extractive"),
    )
    op.add_column("radar_items", sa.Column("analysis_model", sa.Text(), nullable=True))
    op.add_column("radar_items", sa.Column("prompt_version", sa.Text(), nullable=True))
    op.create_index("idx_radar_items_source_id", "radar_items", ["source_id"])
    op.create_index(
        "idx_radar_items_score",
        "radar_items",
        [sa.text("score DESC"), sa.text("published_date DESC NULLS LAST")],
    )
    op.execute(
        """
        CREATE INDEX idx_radar_items_search
        ON radar_items USING gin (
          to_tsvector(
            'simple',
            coalesce(title, '') || ' ' || coalesce(original_title, '') || ' ' ||
            coalesce(product, '') || ' ' || coalesce(summary, '')
          )
        )
        """
    )


def downgrade() -> None:
    op.drop_index("idx_radar_items_search", table_name="radar_items")
    op.drop_index("idx_radar_items_score", table_name="radar_items")
    op.drop_index("idx_radar_items_source_id", table_name="radar_items")
    for column in (
        "prompt_version",
        "analysis_model",
        "analysis_provider",
        "content_hash",
        "rank_reasons",
        "rank",
        "score",
        "confidence",
        "evidence",
        "components",
        "version",
        "author",
        "authority",
        "source_id",
        "channel",
    ):
        op.drop_column("radar_items", column)
