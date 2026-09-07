"""add account location and update fields

Revision ID: 8f2c1a7d4b90
Revises: 5d92d07a9033
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8f2c1a7d4b90"
down_revision: Union[str, Sequence[str], None] = "5d92d07a9033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE users SET is_active = TRUE, "
            "created_at = CURRENT_TIMESTAMP, "
            "updated_at = CURRENT_TIMESTAMP "
            "WHERE is_active IS NULL OR created_at IS NULL "
            "OR updated_at IS NULL"
        )
    )
    op.alter_column(
        "users",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("true"),
    )
    op.alter_column(
        "users",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    op.alter_column(
        "users",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )

    op.add_column(
        "waste_reports",
        sa.Column("latitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "waste_reports",
        sa.Column("longitude", sa.Float(), nullable=True),
    )
    op.add_column(
        "waste_reports",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE waste_reports SET updated_at = created_at "
            "WHERE updated_at IS NULL"
        )
    )
    op.alter_column(
        "waste_reports",
        "updated_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.drop_column("waste_reports", "updated_at")
    op.drop_column("waste_reports", "longitude")
    op.drop_column("waste_reports", "latitude")
    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
    op.drop_column("users", "is_active")
