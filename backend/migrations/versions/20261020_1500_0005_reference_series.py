"""Public reference time series (forecasting / anomaly detection development data).

Revision ID: 0005
Revises: 0004

``reference_series`` records provenance (source URL, commit, licence note, processing note) of a
public dataset; ``reference_series_points`` holds its weekly totals. These rows are clearly
separate from the platform's own operational data and are never mixed into it.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reference_series",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column(
            "unit",
            sa.Enum(
                "kg", "t", "m3", "l", "item", name="quantityunit", native_enum=False, length=12
            ),
            nullable=False,
        ),
        sa.Column(
            "granularity",
            sa.Enum(
                "day", "week", "month", name="forecastgranularity", native_enum=False, length=13
            ),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_commit", sa.String(length=64), nullable=False),
        sa.Column("licence_note", sa.Text(), nullable=False),
        sa.Column("processing_note", sa.Text(), nullable=False),
        sa.Column("first_period", sa.Date(), nullable=False),
        sa.Column("last_period", sa.Date(), nullable=False),
        sa.Column("point_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "granularity IN ('day', 'week', 'month')",
            name=op.f("ck_reference_series_granularity_valid"),
        ),
        sa.CheckConstraint(
            "unit IN ('kg', 't', 'm3', 'l', 'item')", name=op.f("ck_reference_series_unit_valid")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reference_series")),
        sa.UniqueConstraint("key", name=op.f("uq_reference_series_key")),
    )
    op.create_table(
        "reference_series_points",
        sa.Column("series_id", sa.UUID(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=18, scale=3), nullable=False),
        sa.Column("is_interpolated", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "value >= 0", name=op.f("ck_reference_series_points_value_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["reference_series.id"],
            name=op.f("fk_reference_series_points_series_id_reference_series"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reference_series_points")),
        sa.UniqueConstraint("series_id", "period_start", name="series_period"),
    )


def downgrade() -> None:
    op.drop_table("reference_series_points")
    op.drop_table("reference_series")
