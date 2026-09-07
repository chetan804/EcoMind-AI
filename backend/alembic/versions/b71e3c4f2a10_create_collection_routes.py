"""create collection routes

Revision ID: b71e3c4f2a10
Revises: 8f2c1a7d4b90
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b71e3c4f2a10"
down_revision: Union[str, Sequence[str], None] = "8f2c1a7d4b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collection_routes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("collector_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("estimated_distance_km", sa.Float(), nullable=False),
        sa.Column("estimated_duration_minutes", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["collector_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_collection_routes_id",
        "collection_routes",
        ["id"],
        unique=False,
    )
    op.create_table(
        "route_stops",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("collection_id", sa.Integer(), nullable=False),
        sa.Column("stop_order", sa.Integer(), nullable=False),
        sa.Column("distance_from_previous_km", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["collection_id"], ["waste_collections.id"]),
        sa.ForeignKeyConstraint(["route_id"], ["collection_routes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_id"),
    )
    op.create_index("ix_route_stops_id", "route_stops", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_route_stops_id", table_name="route_stops")
    op.drop_table("route_stops")
    op.drop_index("ix_collection_routes_id", table_name="collection_routes")
    op.drop_table("collection_routes")
