"""create environmental monitoring and smart bins

Revision ID: a68c2d9f4e71
Revises: f57b9c2d4e63
Create Date: 2026-09-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a68c2d9f4e71"
down_revision: Union[str, Sequence[str], None] = "f57b9c2d4e63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "environmental_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_environmental_sources_id", "environmental_sources", ["id"], unique=False)

    op.create_table(
        "environmental_readings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("metric", sa.String(length=50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["environmental_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_environmental_readings_id", "environmental_readings", ["id"], unique=False)

    op.create_table(
        "smart_bins",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bin_code", sa.String(length=80), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("fill_level", sa.Float(), nullable=True),
        sa.Column("battery_level", sa.Float(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bin_code"),
    )
    op.create_index("ix_smart_bins_id", "smart_bins", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_smart_bins_id", table_name="smart_bins")
    op.drop_table("smart_bins")
    op.drop_index("ix_environmental_readings_id", table_name="environmental_readings")
    op.drop_table("environmental_readings")
    op.drop_index("ix_environmental_sources_id", table_name="environmental_sources")
    op.drop_table("environmental_sources")
