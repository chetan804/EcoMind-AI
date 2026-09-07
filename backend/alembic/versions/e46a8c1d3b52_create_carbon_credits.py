"""create carbon credits and transactions

Revision ID: e46a8c1d3b52
Revises: d35f7a9b2c41
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e46a8c1d3b52"
down_revision: Union[str, Sequence[str], None] = "d35f7a9b2c41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "carbon_credits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_carbon_credits_id", "carbon_credits", ["id"], unique=False)
    op.create_index("ix_carbon_credits_owner_id", "carbon_credits", ["owner_id"])

    op.create_table(
        "carbon_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("buyer_id", sa.Integer(), nullable=True),
        sa.Column("seller_id", sa.Integer(), nullable=True),
        sa.Column("credit_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("transaction_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["buyer_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["credit_id"], ["carbon_credits.id"]),
        sa.ForeignKeyConstraint(["seller_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_carbon_transactions_id",
        "carbon_transactions",
        ["id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_carbon_transactions_id", table_name="carbon_transactions")
    op.drop_table("carbon_transactions")
    op.drop_index("ix_carbon_credits_owner_id", table_name="carbon_credits")
    op.drop_index("ix_carbon_credits_id", table_name="carbon_credits")
    op.drop_table("carbon_credits")
