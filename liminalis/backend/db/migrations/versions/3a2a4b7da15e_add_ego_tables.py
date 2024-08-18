"""add ego tables

Revision ID: 3a2a4b7da15e
Revises: 0002_invest_initial
Create Date: 2026-05-17 09:56:40.358626

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3a2a4b7da15e"
down_revision: str | Sequence[str] | None = "0002_invest_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ego_records",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column(
            "content_type",
            sa.Text(),
            server_default=sa.text("'text'"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column("record_date", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ego_records_user_date",
        "ego_records",
        ["user_id", sa.literal_column("record_date DESC")],
        unique=False,
    )
    op.create_index(op.f("ix_ego_records_record_date"), "ego_records", ["record_date"], unique=False)
    op.create_index(op.f("ix_ego_records_user_id"), "ego_records", ["user_id"], unique=False)

    op.create_table(
        "ego_sessions",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ego_sessions_user_id"), "ego_sessions", ["user_id"], unique=False)

    op.create_table(
        "ego_messages",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("role_id", sa.Text(), nullable=True),
        sa.Column("role_label", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["ego_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_ego_messages_session_created",
        "ego_messages",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ego_messages_session_id"), "ego_messages", ["session_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ego_messages_session_id"), table_name="ego_messages")
    op.drop_index("idx_ego_messages_session_created", table_name="ego_messages")
    op.drop_table("ego_messages")
    op.drop_index(op.f("ix_ego_sessions_user_id"), table_name="ego_sessions")
    op.drop_table("ego_sessions")
    op.drop_index(op.f("ix_ego_records_user_id"), table_name="ego_records")
    op.drop_index(op.f("ix_ego_records_record_date"), table_name="ego_records")
    op.drop_index("idx_ego_records_user_date", table_name="ego_records")
    op.drop_table("ego_records")
