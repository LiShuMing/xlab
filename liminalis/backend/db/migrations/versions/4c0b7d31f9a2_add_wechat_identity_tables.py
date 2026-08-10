"""add wechat identity tables

Revision ID: 4c0b7d31f9a2
Revises: 3a2a4b7da15e
Create Date: 2026-05-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4c0b7d31f9a2"
down_revision: str | Sequence[str] | None = "3a2a4b7da15e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "liminalis_users",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
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

    op.create_table(
        "liminalis_user_identities",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("app_id", sa.Text(), nullable=False),
        sa.Column("openid", sa.Text(), nullable=False),
        sa.Column("unionid", sa.Text(), nullable=True),
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
        sa.UniqueConstraint(
            "provider",
            "app_id",
            "openid",
            name="uq_liminalis_user_identity_provider_app_openid",
        ),
    )
    op.create_index(
        "idx_liminalis_user_identities_user_provider",
        "liminalis_user_identities",
        ["user_id", "provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_liminalis_user_identities_unionid"),
        "liminalis_user_identities",
        ["unionid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_liminalis_user_identities_user_id"),
        "liminalis_user_identities",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_liminalis_user_identities_user_id"),
        table_name="liminalis_user_identities",
    )
    op.drop_index(
        op.f("ix_liminalis_user_identities_unionid"),
        table_name="liminalis_user_identities",
    )
    op.drop_index(
        "idx_liminalis_user_identities_user_provider",
        table_name="liminalis_user_identities",
    )
    op.drop_table("liminalis_user_identities")
    op.drop_table("liminalis_users")
