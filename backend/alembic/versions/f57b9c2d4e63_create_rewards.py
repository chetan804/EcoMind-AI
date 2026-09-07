"""create rewards

Revision ID: f57b9c2d4e63
Revises: e46a8c1d3b52
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f57b9c2d4e63"
down_revision: Union[str, Sequence[str], None] = "e46a8c1d3b52"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reward_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_reward_accounts_id", "reward_accounts", ["id"], unique=False)

    op.create_table(
        "reward_activities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("activity_type", sa.String(length=50), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "reference",
            name="uq_reward_activity_reference",
        ),
    )
    op.create_index("ix_reward_activities_id", "reward_activities", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_reward_activities_id", table_name="reward_activities")
    op.drop_table("reward_activities")
    op.drop_index("ix_reward_accounts_id", table_name="reward_accounts")
    op.drop_table("reward_accounts")
