"""create municipalities and service areas

Revision ID: 9c4e7b1a2d6f
Revises: b82d1f6a4c90
Create Date: 2026-09-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c4e7b1a2d6f"
down_revision: Union[str, Sequence[str], None] = "b82d1f6a4c90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "municipalities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("region", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=80), nullable=True),
        sa.Column("contact_email", sa.String(length=150), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_municipalities_id", "municipalities", ["id"], unique=False)
    op.create_index("ix_municipalities_code", "municipalities", ["code"], unique=True)
    op.create_index("ix_municipalities_external_id", "municipalities", ["external_id"], unique=True)

    op.create_table(
        "service_areas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("municipality_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
        sa.Column("external_id", sa.String(length=80), nullable=True),
        sa.Column("boundary_json", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "municipality_id",
            "code",
            name="uq_service_area_municipality_code",
        ),
    )
    op.create_index("ix_service_areas_id", "service_areas", ["id"], unique=False)
    op.create_index("ix_service_areas_external_id", "service_areas", ["external_id"], unique=False)

    op.create_table(
        "municipal_sync_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("municipality_id", sa.Integer(), nullable=False),
        sa.Column("sync_type", sa.String(length=60), nullable=False),
        sa.Column("provider", sa.String(length=60), server_default="internal", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="queued", nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_municipal_sync_logs_id", "municipal_sync_logs", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_municipal_sync_logs_id", table_name="municipal_sync_logs")
    op.drop_table("municipal_sync_logs")
    op.drop_index("ix_service_areas_external_id", table_name="service_areas")
    op.drop_index("ix_service_areas_id", table_name="service_areas")
    op.drop_table("service_areas")
    op.drop_index("ix_municipalities_external_id", table_name="municipalities")
    op.drop_index("ix_municipalities_code", table_name="municipalities")
    op.drop_index("ix_municipalities_id", table_name="municipalities")
    op.drop_table("municipalities")