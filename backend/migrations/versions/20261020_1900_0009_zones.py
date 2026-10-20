"""Zones: named service areas, and an optional zone on each facility.

Revision ID: 0009
Revises: 0008

Zones carry no boundary geometry (the platform has no verified map data). Facilities may belong to
one zone; the column is nullable so existing rows stay valid.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "zones",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "zone_type",
            sa.Enum(
                "residential",
                "commercial",
                "industrial",
                "mixed_use",
                "institutional",
                "other",
                name="zonetype",
                native_enum=False,
                length=21,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
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
        sa.CheckConstraint(
            "zone_type IN ('residential', 'commercial', 'industrial', 'mixed_use', "
            "'institutional', 'other')",
            name=op.f("ck_zones_zone_type_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_zones")),
        sa.UniqueConstraint("code", name="uq_zones_code"),
    )
    op.create_index(op.f("ix_zones_zone_type"), "zones", ["zone_type"])
    op.create_index(op.f("ix_zones_is_active"), "zones", ["is_active"])
    op.add_column("facilities", sa.Column("zone_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_facilities_zone_id"), "facilities", ["zone_id"])
    op.create_foreign_key(
        op.f("fk_facilities_zone_id_zones"), "facilities", "zones", ["zone_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_facilities_zone_id_zones", "facilities", type_="foreignkey")
    op.drop_index(op.f("ix_facilities_zone_id"), table_name="facilities")
    op.drop_column("facilities", "zone_id")
    op.drop_table("zones")
