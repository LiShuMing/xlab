"""add ego memory and profile tables

Revision ID: 5d2f8a7c1b0e
Revises: 4c0b7d31f9a2
Create Date: 2026-06-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "5d2f8a7c1b0e"
down_revision: str | Sequence[str] | None = "4c0b7d31f9a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "ego_memories",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(), nullable=True),
        sa.Column(
            "meta",
            sa.dialects.postgresql.JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ego_memories_user_id"), "ego_memories", ["user_id"], unique=False)
    op.create_index(op.f("ix_ego_memories_role_id"), "ego_memories", ["role_id"], unique=False)
    op.create_index(
        "idx_ego_memories_user_role_created",
        "ego_memories",
        ["user_id", "role_id", sa.literal_column("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "ego_profiles",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Text(), server_default=sa.text("'global'"), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_ego_profiles_user_role"),
    )
    op.create_index(op.f("ix_ego_profiles_user_id"), "ego_profiles", ["user_id"], unique=False)
    op.create_index("idx_ego_profiles_user_role", "ego_profiles", ["user_id", "role_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_ego_profiles_user_role", table_name="ego_profiles")
    op.drop_index(op.f("ix_ego_profiles_user_id"), table_name="ego_profiles")
    op.drop_table("ego_profiles")

    op.drop_index("idx_ego_memories_user_role_created", table_name="ego_memories")
    op.drop_index(op.f("ix_ego_memories_role_id"), table_name="ego_memories")
    op.drop_index(op.f("ix_ego_memories_user_id"), table_name="ego_memories")
    op.drop_table("ego_memories")
