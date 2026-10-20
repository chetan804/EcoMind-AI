"""Vehicle location events (append-only) and the tracking permissions.

Revision ID: 0011
Revises: 0010

``vehicle_location_events`` rows are immutable: a BEFORE UPDATE trigger (reusing the function from
0007) rejects every UPDATE. Deletes stay possible on purpose: the retention job and the simulator
reset remove whole rows.

The permission and role-grant rows are literal copies of what ``app.modules.users.rbac`` defines for
tracking at this revision (migrations never import application code).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "fleet:track": "Report positions of the vehicle the user is currently assigned to",
    "fleet:simulate": "Write labelled simulator positions (demonstration environments only)",
}
GRANTS = {
    "collector": ("fleet:track",),
    "manager": ("fleet:simulate",),
    "administrator": tuple(PERMISSIONS),
}


def upgrade() -> None:
    op.create_table(
        "vehicle_location_events",
        sa.Column("vehicle_id", sa.UUID(), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "gps_device",
                "mobile_client",
                "imported",
                "simulator",
                name="locationsource",
                native_enum=False,
                length=21,
            ),
            nullable=False,
        ),
        sa.Column(
            "quality",
            sa.Enum(
                "accepted", "out_of_order", name="locationquality", native_enum=False, length=20
            ),
            nullable=False,
        ),
        sa.Column("accuracy_m", sa.Numeric(precision=9, scale=2), nullable=True),
        sa.Column("speed_kph", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("heading_deg", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("sequence", sa.BigInteger(), nullable=True),
        sa.Column("collection_task_id", sa.UUID(), nullable=True),
        sa.Column("route_plan_id", sa.UUID(), nullable=True),
        sa.Column("reported_by_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "quality IN ('accepted', 'out_of_order')",
            name=op.f("ck_vehicle_location_events_quality_valid"),
        ),
        sa.CheckConstraint(
            "source IN ('gps_device', 'mobile_client', 'imported', 'simulator')",
            name=op.f("ck_vehicle_location_events_source_valid"),
        ),
        sa.CheckConstraint(
            "accuracy_m IS NULL OR accuracy_m >= 0",
            name=op.f("ck_vehicle_location_events_accuracy_non_negative"),
        ),
        sa.CheckConstraint(
            "heading_deg IS NULL OR (heading_deg >= 0 AND heading_deg < 360)",
            name=op.f("ck_vehicle_location_events_heading_range"),
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name=op.f("ck_vehicle_location_events_latitude_range")
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180",
            name=op.f("ck_vehicle_location_events_longitude_range"),
        ),
        sa.CheckConstraint(
            "sequence IS NULL OR sequence >= 0",
            name=op.f("ck_vehicle_location_events_sequence_non_negative"),
        ),
        sa.CheckConstraint(
            "speed_kph IS NULL OR (speed_kph >= 0 AND speed_kph <= 300)",
            name=op.f("ck_vehicle_location_events_speed_range"),
        ),
        sa.ForeignKeyConstraint(
            ["collection_task_id"],
            ["collection_tasks.id"],
            name=op.f("fk_vehicle_location_events_collection_task_id_collection_tasks"),
        ),
        sa.ForeignKeyConstraint(
            ["reported_by_id"],
            ["users.id"],
            name=op.f("fk_vehicle_location_events_reported_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["route_plan_id"],
            ["route_plans.id"],
            name=op.f("fk_vehicle_location_events_route_plan_id_route_plans"),
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["fleet_vehicles.id"],
            name=op.f("fk_vehicle_location_events_vehicle_id_fleet_vehicles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vehicle_location_events")),
        sa.UniqueConstraint(
            "vehicle_id", "source", "recorded_at", name="uq_vehicle_location_events_identity"
        ),
    )
    op.create_index(
        op.f("ix_vehicle_location_events_collection_task_id"),
        "vehicle_location_events",
        ["collection_task_id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_location_events_recorded_at",
        "vehicle_location_events",
        ["recorded_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vehicle_location_events_reported_by_id"),
        "vehicle_location_events",
        ["reported_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vehicle_location_events_route_plan_id"),
        "vehicle_location_events",
        ["route_plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_vehicle_location_events_vehicle_recorded",
        "vehicle_location_events",
        ["vehicle_id", sa.literal_column("recorded_at DESC")],
        unique=False,
    )
    op.create_index(
        "uq_vehicle_location_events_sequence",
        "vehicle_location_events",
        ["vehicle_id", "source", "sequence"],
        unique=True,
        postgresql_where=sa.text("sequence IS NOT NULL"),
    )
    op.execute(
        "CREATE TRIGGER vehicle_location_events_immutable BEFORE UPDATE ON vehicle_location_events "
        "FOR EACH ROW EXECUTE FUNCTION prevent_ledger_mutation()"
    )

    conn = op.get_bind()
    for code, description in PERMISSIONS.items():
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, description) VALUES (:code, :description) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "description": description},
        )
    for role, codes in GRANTS.items():
        for code in codes:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r, permissions p "
                    "WHERE r.name = :role AND p.code = :code ON CONFLICT DO NOTHING"
                ),
                {"role": role, "code": code},
            )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": list(PERMISSIONS)}
    )
    op.execute(
        "DROP TRIGGER IF EXISTS vehicle_location_events_immutable ON vehicle_location_events"
    )
    op.drop_index(
        "uq_vehicle_location_events_sequence",
        table_name="vehicle_location_events",
        postgresql_where=sa.text("sequence IS NOT NULL"),
    )
    op.drop_index(
        "ix_vehicle_location_events_vehicle_recorded", table_name="vehicle_location_events"
    )
    op.drop_index(
        op.f("ix_vehicle_location_events_route_plan_id"), table_name="vehicle_location_events"
    )
    op.drop_index(
        op.f("ix_vehicle_location_events_reported_by_id"), table_name="vehicle_location_events"
    )
    op.drop_index("ix_vehicle_location_events_recorded_at", table_name="vehicle_location_events")
    op.drop_index(
        op.f("ix_vehicle_location_events_collection_task_id"), table_name="vehicle_location_events"
    )
    op.drop_table("vehicle_location_events")
