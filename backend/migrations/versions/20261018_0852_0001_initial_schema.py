"""Initial schema: all domain tables (see docs/database/schema-overview.md).

Revision ID: 0001
Revises:
Create Date: 2026-10-18 08:52:07.311314
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "classification_model_versions",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "candidate",
                "active",
                "retired",
                name="modelversionstatus",
                native_enum=False,
                length=17,
            ),
            server_default="candidate",
            nullable=False,
        ),
        sa.Column("framework", sa.String(length=50), nullable=True),
        sa.Column("artifact_manifest_sha256", sa.String(length=64), nullable=True),
        sa.Column("evaluation_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trained_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('candidate', 'active', 'retired')",
            name=op.f("ck_classification_model_versions_status_valid"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classification_model_versions")),
        sa.UniqueConstraint(
            "name", "version", name="uq_classification_model_versions_name_version"
        ),
    )
    op.create_table(
        "facilities",
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "facility_type",
            sa.Enum(
                "processing_center",
                "depot",
                "transfer_station",
                "drop_off_point",
                name="facilitytype",
                native_enum=False,
                length=25,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                "maintenance",
                name="facilitystatus",
                native_enum=False,
                length=19,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("address_line", sa.String(length=300), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("country_code", sa.String(length=2), nullable=True),
        sa.Column("daily_capacity_kg", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=True),
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
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.CheckConstraint(
            "facility_type IN ('processing_center', 'depot', 'transfer_station', 'drop_off_point')",
            name=op.f("ck_facilities_facility_type_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('active', 'inactive', 'maintenance')",
            name=op.f("ck_facilities_status_valid"),
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name=op.f("ck_facilities_geo_point_complete"),
        ),
        sa.CheckConstraint(
            "daily_capacity_kg IS NULL OR daily_capacity_kg > 0",
            name=op.f("ck_facilities_capacity_positive"),
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name=op.f("ck_facilities_latitude_range")
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_facilities_longitude_range")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_facilities")),
        sa.UniqueConstraint("code", name=op.f("uq_facilities_code")),
    )
    op.create_index(
        op.f("ix_facilities_facility_type"), "facilities", ["facility_type"], unique=False
    )
    op.create_table(
        "material_categories",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_material_categories")),
        sa.UniqueConstraint("code", name=op.f("uq_material_categories_code")),
    )
    op.create_table(
        "permissions",
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permissions")),
        sa.UniqueConstraint("code", name=op.f("uq_permissions_code")),
    )
    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default="false", nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("name", name=op.f("uq_roles_name")),
    )
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(
        "uq_users_email_lower", "users", [sa.literal_column("lower(email)")], unique=True
    )
    op.create_table(
        "anomaly_alerts",
        sa.Column("metric", sa.String(length=64), nullable=False),
        sa.Column(
            "unit",
            sa.Enum(
                "kg", "t", "m3", "l", "item", name="quantityunit", native_enum=False, length=12
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "info", "warning", "critical", name="anomalyseverity", native_enum=False, length=16
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "acknowledged",
                "resolved",
                "false_positive",
                name="alertstatus",
                native_enum=False,
                length=22,
            ),
            server_default="open",
            nullable=False,
        ),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("material_category_id", sa.UUID(), nullable=True),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_value", sa.Numeric(precision=16, scale=3), nullable=False),
        sa.Column("expected_value", sa.Numeric(precision=16, scale=3), nullable=False),
        sa.Column("threshold_value", sa.Numeric(precision=16, scale=3), nullable=True),
        sa.Column("detector_name", sa.String(length=100), nullable=False),
        sa.Column("detector_version", sa.String(length=50), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_by_id", sa.UUID(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
            "severity IN ('info', 'warning', 'critical')",
            name=op.f("ck_anomaly_alerts_severity_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'resolved', 'false_positive')",
            name=op.f("ck_anomaly_alerts_status_valid"),
        ),
        sa.CheckConstraint(
            "unit IN ('kg', 't', 'm3', 'l', 'item')", name=op.f("ck_anomaly_alerts_unit_valid")
        ),
        sa.CheckConstraint(
            "length(explanation) > 0", name=op.f("ck_anomaly_alerts_explanation_required")
        ),
        sa.CheckConstraint(
            "window_end > window_start", name=op.f("ck_anomaly_alerts_window_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by_id"],
            ["users.id"],
            name=op.f("fk_anomaly_alerts_acknowledged_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_anomaly_alerts_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["material_category_id"],
            ["material_categories.id"],
            name=op.f("fk_anomaly_alerts_material_category_id_material_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_anomaly_alerts")),
    )
    op.create_index(
        op.f("ix_anomaly_alerts_acknowledged_by_id"),
        "anomaly_alerts",
        ["acknowledged_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_anomaly_alerts_detected_at"), "anomaly_alerts", ["detected_at"], unique=False
    )
    op.create_index(
        op.f("ix_anomaly_alerts_facility_id"), "anomaly_alerts", ["facility_id"], unique=False
    )
    op.create_index(
        op.f("ix_anomaly_alerts_material_category_id"),
        "anomaly_alerts",
        ["material_category_id"],
        unique=False,
    )
    op.create_index(op.f("ix_anomaly_alerts_metric"), "anomaly_alerts", ["metric"], unique=False)
    op.create_index(op.f("ix_anomaly_alerts_status"), "anomaly_alerts", ["status"], unique=False)
    op.create_table(
        "audit_logs",
        sa.Column("actor_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_actor_id"), "audit_logs", ["actor_id"], unique=False)
    op.create_index(
        "ix_audit_logs_entity_type_entity_id",
        "audit_logs",
        ["entity_type", "entity_id"],
        unique=False,
    )
    op.create_index("ix_audit_logs_occurred_at", "audit_logs", ["occurred_at"], unique=False)
    op.create_table(
        "auth_sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "family_id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
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
            "expires_at > created_at", name=op.f("ck_auth_sessions_expiry_after_creation")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_auth_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_auth_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_auth_sessions_token_hash")),
    )
    op.create_index(
        op.f("ix_auth_sessions_family_id"), "auth_sessions", ["family_id"], unique=False
    )
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)
    op.create_table(
        "fleet_vehicles",
        sa.Column("registration_number", sa.String(length=32), nullable=False),
        sa.Column(
            "vehicle_type",
            sa.Enum(
                "compactor_truck",
                "tipper_truck",
                "van",
                "cargo_bike",
                "other",
                name="vehicletype",
                native_enum=False,
                length=23,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "available",
                "in_service",
                "maintenance",
                "retired",
                name="vehiclestatus",
                native_enum=False,
                length=19,
            ),
            server_default="available",
            nullable=False,
        ),
        sa.Column("capacity_kg", sa.Numeric(precision=12, scale=3), nullable=False),
        sa.Column("home_facility_id", sa.UUID(), nullable=True),
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
            "status IN ('available', 'in_service', 'maintenance', 'retired')",
            name=op.f("ck_fleet_vehicles_status_valid"),
        ),
        sa.CheckConstraint(
            "vehicle_type IN ('compactor_truck', 'tipper_truck', 'van', 'cargo_bike', 'other')",
            name=op.f("ck_fleet_vehicles_vehicle_type_valid"),
        ),
        sa.CheckConstraint("capacity_kg > 0", name=op.f("ck_fleet_vehicles_capacity_positive")),
        sa.ForeignKeyConstraint(
            ["home_facility_id"],
            ["facilities.id"],
            name=op.f("fk_fleet_vehicles_home_facility_id_facilities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fleet_vehicles")),
        sa.UniqueConstraint(
            "registration_number", name=op.f("uq_fleet_vehicles_registration_number")
        ),
    )
    op.create_index(
        op.f("ix_fleet_vehicles_home_facility_id"),
        "fleet_vehicles",
        ["home_facility_id"],
        unique=False,
    )
    op.create_index(op.f("ix_fleet_vehicles_status"), "fleet_vehicles", ["status"], unique=False)
    op.create_table(
        "forecast_results",
        sa.Column("metric", sa.String(length=64), nullable=False),
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
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("material_category_id", sa.UUID(), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("predicted_value", sa.Numeric(precision=16, scale=3), nullable=False),
        sa.Column("lower_bound", sa.Numeric(precision=16, scale=3), nullable=True),
        sa.Column("upper_bound", sa.Numeric(precision=16, scale=3), nullable=True),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "granularity IN ('day', 'week', 'month')",
            name=op.f("ck_forecast_results_granularity_valid"),
        ),
        sa.CheckConstraint(
            "unit IN ('kg', 't', 'm3', 'l', 'item')", name=op.f("ck_forecast_results_unit_valid")
        ),
        sa.CheckConstraint(
            "lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound",
            name=op.f("ck_forecast_results_interval_ordered"),
        ),
        sa.CheckConstraint(
            "period_end > period_start", name=op.f("ck_forecast_results_period_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_forecast_results_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["material_category_id"],
            ["material_categories.id"],
            name=op.f("fk_forecast_results_material_category_id_material_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_results")),
    )
    op.create_index(
        op.f("ix_forecast_results_facility_id"), "forecast_results", ["facility_id"], unique=False
    )
    op.create_index(
        op.f("ix_forecast_results_material_category_id"),
        "forecast_results",
        ["material_category_id"],
        unique=False,
    )
    op.create_index(
        "ix_forecast_results_metric_period_start",
        "forecast_results",
        ["metric", "period_start"],
        unique=False,
    )
    op.create_table(
        "notifications",
        sa.Column("recipient_id", sa.UUID(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "collection",
                "report",
                "incident",
                "anomaly",
                "reward",
                "system",
                name="notificationcategory",
                native_enum=False,
                length=18,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.UUID(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('collection', 'report', 'incident', 'anomaly', 'reward', 'system')",
            name=op.f("ck_notifications_category_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["users.id"],
            name=op.f("fk_notifications_recipient_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        "ix_notifications_recipient_id_read_at",
        "notifications",
        ["recipient_id", "read_at"],
        unique=False,
    )
    op.create_table(
        "reward_ledger_entries",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "entry_type",
            sa.Enum(
                "earned",
                "redeemed",
                "adjustment",
                "reversal",
                name="ledgerentrytype",
                native_enum=False,
                length=18,
            ),
            nullable=False,
        ),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("impact_weight_kg", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column(
            "source_type",
            sa.Enum(
                "waste_report",
                "collection_task",
                "recovery_record",
                "community_incident",
                "manual",
                name="ledgersourcetype",
                native_enum=False,
                length=26,
            ),
            nullable=False,
        ),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("reverses_entry_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(entry_type = 'reversal') = (reverses_entry_id IS NOT NULL)",
            name=op.f("ck_reward_ledger_entries_reversal_references_entry"),
        ),
        sa.CheckConstraint(
            "entry_type IN ('earned', 'redeemed', 'adjustment', 'reversal')",
            name=op.f("ck_reward_ledger_entries_entry_type_valid"),
        ),
        sa.CheckConstraint(
            "source_type IN ('waste_report', 'collection_task', 'recovery_record', 'community_incident', 'manual')",
            name=op.f("ck_reward_ledger_entries_source_type_valid"),
        ),
        sa.CheckConstraint(
            "impact_weight_kg IS NULL OR impact_weight_kg >= 0",
            name=op.f("ck_reward_ledger_entries_impact_non_negative"),
        ),
        sa.CheckConstraint("points <> 0", name=op.f("ck_reward_ledger_entries_points_non_zero")),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_reward_ledger_entries_created_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["reverses_entry_id"],
            ["reward_ledger_entries.id"],
            name=op.f("fk_reward_ledger_entries_reverses_entry_id_reward_ledger_entries"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_reward_ledger_entries_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reward_ledger_entries")),
    )
    op.create_index(
        op.f("ix_reward_ledger_entries_created_by_id"),
        "reward_ledger_entries",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reward_ledger_entries_reverses_entry_id"),
        "reward_ledger_entries",
        ["reverses_entry_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reward_ledger_entries_user_id"), "reward_ledger_entries", ["user_id"], unique=False
    )
    op.create_index(
        "uq_reward_ledger_entries_idempotency",
        "reward_ledger_entries",
        ["user_id", "source_type", "source_id", "entry_type"],
        unique=True,
        postgresql_where=sa.text("source_id IS NOT NULL AND entry_type = 'earned'"),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("permission_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["permissions.id"],
            name=op.f("fk_role_permissions_permission_id_permissions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"],
            ["roles.id"],
            name=op.f("fk_role_permissions_role_id_roles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("role_id", "permission_id", name=op.f("pk_role_permissions")),
    )
    op.create_index(
        op.f("ix_role_permissions_permission_id"),
        "role_permissions",
        ["permission_id"],
        unique=False,
    )
    op.create_table(
        "sorting_guidance",
        sa.Column("material_category_id", sa.UUID(), nullable=False),
        sa.Column(
            "disposal_method",
            sa.Enum(
                "recycle",
                "compost",
                "reuse",
                "landfill",
                "hazardous_drop_off",
                "e_waste_drop_off",
                "special_collection",
                name="disposalmethod",
                native_enum=False,
                length=26,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("preparation_notes", sa.Text(), nullable=True),
        sa.Column("source_reference", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
            "disposal_method IN ('recycle', 'compost', 'reuse', 'landfill', 'hazardous_drop_off', 'e_waste_drop_off', 'special_collection')",
            name=op.f("ck_sorting_guidance_disposal_method_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["material_category_id"],
            ["material_categories.id"],
            name=op.f("fk_sorting_guidance_material_category_id_material_categories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sorting_guidance")),
    )
    op.create_index(
        op.f("ix_sorting_guidance_material_category_id"),
        "sorting_guidance",
        ["material_category_id"],
        unique=False,
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_user_roles_role_id_roles"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_user_roles_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "role_id", name=op.f("pk_user_roles")),
    )
    op.create_index(op.f("ix_user_roles_role_id"), "user_roles", ["role_id"], unique=False)
    op.create_table(
        "waste_reports",
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "submitted",
                "under_review",
                "verified",
                "rejected",
                "closed",
                name="wastereportstatus",
                native_enum=False,
                length=20,
            ),
            server_default="submitted",
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address_text", sa.String(length=500), nullable=True),
        sa.Column("estimated_weight_kg", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column(
            "reported_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.CheckConstraint(
            "status IN ('submitted', 'under_review', 'verified', 'rejected', 'closed')",
            name=op.f("ck_waste_reports_status_valid"),
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name=op.f("ck_waste_reports_geo_point_complete"),
        ),
        sa.CheckConstraint(
            "estimated_weight_kg IS NULL OR estimated_weight_kg >= 0",
            name=op.f("ck_waste_reports_weight_non_negative"),
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name=op.f("ck_waste_reports_latitude_range")
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_waste_reports_longitude_range")
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"], ["users.id"], name=op.f("fk_waste_reports_reporter_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_waste_reports")),
    )
    op.create_index(
        op.f("ix_waste_reports_reported_at"), "waste_reports", ["reported_at"], unique=False
    )
    op.create_index(
        op.f("ix_waste_reports_reporter_id"), "waste_reports", ["reporter_id"], unique=False
    )
    op.create_index(op.f("ix_waste_reports_status"), "waste_reports", ["status"], unique=False)
    op.create_table(
        "collection_tasks",
        sa.Column("waste_report_id", sa.UUID(), nullable=True),
        sa.Column("destination_facility_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "assigned",
                "in_progress",
                "completed",
                "failed",
                "cancelled",
                name="collectiontaskstatus",
                native_enum=False,
                length=19,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum(
                "low", "normal", "high", "urgent", name="taskpriority", native_enum=False, length=14
            ),
            server_default="normal",
            nullable=False,
        ),
        sa.Column("address_text", sa.String(length=500), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name=op.f("ck_collection_tasks_priority_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled')",
            name=op.f("ck_collection_tasks_status_valid"),
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name=op.f("ck_collection_tasks_geo_point_complete"),
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name=op.f("ck_collection_tasks_latitude_range")
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_collection_tasks_longitude_range")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_collection_tasks_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["destination_facility_id"],
            ["facilities.id"],
            name=op.f("fk_collection_tasks_destination_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["waste_report_id"],
            ["waste_reports.id"],
            name=op.f("fk_collection_tasks_waste_report_id_waste_reports"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_tasks")),
    )
    op.create_index(
        op.f("ix_collection_tasks_created_by_id"),
        "collection_tasks",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collection_tasks_destination_facility_id"),
        "collection_tasks",
        ["destination_facility_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collection_tasks_due_at"), "collection_tasks", ["due_at"], unique=False
    )
    op.create_index(
        op.f("ix_collection_tasks_status"), "collection_tasks", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_collection_tasks_waste_report_id"),
        "collection_tasks",
        ["waste_report_id"],
        unique=False,
    )
    op.create_table(
        "media_assets",
        sa.Column("uploaded_by_id", sa.UUID(), nullable=False),
        sa.Column("waste_report_id", sa.UUID(), nullable=True),
        sa.Column("storage_backend", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("width_px", sa.Integer(), nullable=True),
        sa.Column("height_px", sa.Integer(), nullable=True),
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
        sa.CheckConstraint("length(sha256) = 64", name=op.f("ck_media_assets_sha256_hex_length")),
        sa.CheckConstraint("size_bytes > 0", name=op.f("ck_media_assets_size_positive")),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"], ["users.id"], name=op.f("fk_media_assets_uploaded_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["waste_report_id"],
            ["waste_reports.id"],
            name=op.f("fk_media_assets_waste_report_id_waste_reports"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media_assets")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_media_assets_storage_key")),
    )
    op.create_index(op.f("ix_media_assets_sha256"), "media_assets", ["sha256"], unique=False)
    op.create_index(
        op.f("ix_media_assets_uploaded_by_id"), "media_assets", ["uploaded_by_id"], unique=False
    )
    op.create_index(
        op.f("ix_media_assets_waste_report_id"), "media_assets", ["waste_report_id"], unique=False
    )
    op.create_table(
        "route_plans",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "published",
                "in_progress",
                "completed",
                "cancelled",
                name="routeplanstatus",
                native_enum=False,
                length=19,
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("vehicle_id", sa.UUID(), nullable=True),
        sa.Column("driver_id", sa.UUID(), nullable=True),
        sa.Column("start_facility_id", sa.UUID(), nullable=True),
        sa.Column("end_facility_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("total_distance_km", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("estimated_duration_min", sa.Integer(), nullable=True),
        sa.Column("optimizer", sa.String(length=100), nullable=True),
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
            "status IN ('draft', 'published', 'in_progress', 'completed', 'cancelled')",
            name=op.f("ck_route_plans_status_valid"),
        ),
        sa.CheckConstraint(
            "estimated_duration_min IS NULL OR estimated_duration_min >= 0",
            name=op.f("ck_route_plans_duration_non_negative"),
        ),
        sa.CheckConstraint(
            "total_distance_km IS NULL OR total_distance_km >= 0",
            name=op.f("ck_route_plans_distance_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_route_plans_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["driver_id"], ["users.id"], name=op.f("fk_route_plans_driver_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["end_facility_id"],
            ["facilities.id"],
            name=op.f("fk_route_plans_end_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["start_facility_id"],
            ["facilities.id"],
            name=op.f("fk_route_plans_start_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["fleet_vehicles.id"],
            name=op.f("fk_route_plans_vehicle_id_fleet_vehicles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_route_plans")),
    )
    op.create_index(
        op.f("ix_route_plans_created_by_id"), "route_plans", ["created_by_id"], unique=False
    )
    op.create_index(op.f("ix_route_plans_driver_id"), "route_plans", ["driver_id"], unique=False)
    op.create_index(
        op.f("ix_route_plans_end_facility_id"), "route_plans", ["end_facility_id"], unique=False
    )
    op.create_index(
        op.f("ix_route_plans_planned_date"), "route_plans", ["planned_date"], unique=False
    )
    op.create_index(
        op.f("ix_route_plans_start_facility_id"), "route_plans", ["start_facility_id"], unique=False
    )
    op.create_index(op.f("ix_route_plans_status"), "route_plans", ["status"], unique=False)
    op.create_index(op.f("ix_route_plans_vehicle_id"), "route_plans", ["vehicle_id"], unique=False)
    op.create_table(
        "classification_predictions",
        sa.Column("media_asset_id", sa.UUID(), nullable=False),
        sa.Column("model_version_id", sa.UUID(), nullable=False),
        sa.Column("object_label", sa.String(length=200), nullable=True),
        sa.Column("object_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("material_category_id", sa.UUID(), nullable=False),
        sa.Column("material_confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column(
            "review_status",
            sa.Enum(
                "unreviewed",
                "confirmed",
                "corrected",
                "rejected",
                name="reviewstatus",
                native_enum=False,
                length=18,
            ),
            server_default="unreviewed",
            nullable=False,
        ),
        sa.Column("reviewed_material_category_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_by_id", sa.UUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
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
            "(review_status = 'corrected') = (reviewed_material_category_id IS NOT NULL)",
            name=op.f("ck_classification_predictions_correction_has_category"),
        ),
        sa.CheckConstraint(
            "(review_status = 'unreviewed') = (reviewed_at IS NULL)",
            name=op.f("ck_classification_predictions_review_timestamp_consistent"),
        ),
        sa.CheckConstraint(
            "review_status IN ('unreviewed', 'confirmed', 'corrected', 'rejected')",
            name=op.f("ck_classification_predictions_review_status_valid"),
        ),
        sa.CheckConstraint(
            "material_confidence BETWEEN 0 AND 1",
            name=op.f("ck_classification_predictions_material_confidence_range"),
        ),
        sa.CheckConstraint(
            "object_confidence BETWEEN 0 AND 1",
            name=op.f("ck_classification_predictions_object_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["material_category_id"],
            ["material_categories.id"],
            name=op.f("fk_classification_predictions_material_category_id_material_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["media_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_classification_predictions_media_asset_id_media_assets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["model_version_id"],
            ["classification_model_versions.id"],
            name=op.f(
                "fk_classification_predictions_model_version_id_classification_model_versions"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"],
            ["users.id"],
            name=op.f("fk_classification_predictions_reviewed_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_material_category_id"],
            ["material_categories.id"],
            name=op.f(
                "fk_classification_predictions_reviewed_material_category_id_material_categories"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_classification_predictions")),
        sa.UniqueConstraint(
            "media_asset_id",
            "model_version_id",
            name="uq_classification_predictions_media_asset_id_model_version_id",
        ),
    )
    op.create_index(
        op.f("ix_classification_predictions_material_category_id"),
        "classification_predictions",
        ["material_category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classification_predictions_media_asset_id"),
        "classification_predictions",
        ["media_asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classification_predictions_model_version_id"),
        "classification_predictions",
        ["model_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classification_predictions_review_status"),
        "classification_predictions",
        ["review_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classification_predictions_reviewed_by_id"),
        "classification_predictions",
        ["reviewed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_classification_predictions_reviewed_material_category_id"),
        "classification_predictions",
        ["reviewed_material_category_id"],
        unique=False,
    )
    op.create_table(
        "collection_assignments",
        sa.Column("collection_task_id", sa.UUID(), nullable=False),
        sa.Column("assignee_id", sa.UUID(), nullable=False),
        sa.Column("vehicle_id", sa.UUID(), nullable=True),
        sa.Column("assigned_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("unassigned_at", sa.DateTime(timezone=True), nullable=True),
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
            "unassigned_at IS NULL OR unassigned_at >= assigned_at",
            name=op.f("ck_collection_assignments_unassigned_after_assigned"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_id"],
            ["users.id"],
            name=op.f("fk_collection_assignments_assigned_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["assignee_id"], ["users.id"], name=op.f("fk_collection_assignments_assignee_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["collection_task_id"],
            ["collection_tasks.id"],
            name=op.f("fk_collection_assignments_collection_task_id_collection_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vehicle_id"],
            ["fleet_vehicles.id"],
            name=op.f("fk_collection_assignments_vehicle_id_fleet_vehicles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_assignments")),
    )
    op.create_index(
        op.f("ix_collection_assignments_assigned_by_id"),
        "collection_assignments",
        ["assigned_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collection_assignments_assignee_id"),
        "collection_assignments",
        ["assignee_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collection_assignments_collection_task_id"),
        "collection_assignments",
        ["collection_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collection_assignments_vehicle_id"),
        "collection_assignments",
        ["vehicle_id"],
        unique=False,
    )
    op.create_index(
        "uq_collection_assignments_active_task",
        "collection_assignments",
        ["collection_task_id"],
        unique=True,
        postgresql_where=sa.text("unassigned_at IS NULL"),
    )
    op.create_table(
        "collection_events",
        sa.Column("collection_task_id", sa.UUID(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "arrived",
                "collected",
                "skipped",
                "contaminated",
                "delivered_to_facility",
                name="collectioneventtype",
                native_enum=False,
                length=29,
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by_id", sa.UUID(), nullable=False),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("collected_weight_kg", sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.CheckConstraint(
            "event_type IN ('arrived', 'collected', 'skipped', 'contaminated', 'delivered_to_facility')",
            name=op.f("ck_collection_events_event_type_valid"),
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name=op.f("ck_collection_events_geo_point_complete"),
        ),
        sa.CheckConstraint(
            "collected_weight_kg IS NULL OR collected_weight_kg >= 0",
            name=op.f("ck_collection_events_weight_non_negative"),
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name=op.f("ck_collection_events_latitude_range")
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_collection_events_longitude_range")
        ),
        sa.ForeignKeyConstraint(
            ["collection_task_id"],
            ["collection_tasks.id"],
            name=op.f("fk_collection_events_collection_task_id_collection_tasks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_collection_events_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_id"], ["users.id"], name=op.f("fk_collection_events_recorded_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_events")),
    )
    op.create_index(
        op.f("ix_collection_events_collection_task_id"),
        "collection_events",
        ["collection_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collection_events_facility_id"), "collection_events", ["facility_id"], unique=False
    )
    op.create_index(
        op.f("ix_collection_events_occurred_at"), "collection_events", ["occurred_at"], unique=False
    )
    op.create_index(
        op.f("ix_collection_events_recorded_by_id"),
        "collection_events",
        ["recorded_by_id"],
        unique=False,
    )
    op.create_table(
        "collection_task_status_history",
        sa.Column("collection_task_id", sa.UUID(), nullable=False),
        sa.Column(
            "from_status",
            sa.Enum(
                "pending",
                "assigned",
                "in_progress",
                "completed",
                "failed",
                "cancelled",
                name="collectiontaskstatus",
                native_enum=False,
                length=19,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum(
                "pending",
                "assigned",
                "in_progress",
                "completed",
                "failed",
                "cancelled",
                name="collectiontaskstatus",
                native_enum=False,
                length=19,
            ),
            nullable=False,
        ),
        sa.Column("changed_by_id", sa.UUID(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "from_status IN ('pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled')",
            name=op.f("ck_collection_task_status_history_from_status_valid"),
        ),
        sa.CheckConstraint(
            "to_status IN ('pending', 'assigned', 'in_progress', 'completed', 'failed', 'cancelled')",
            name=op.f("ck_collection_task_status_history_to_status_valid"),
        ),
        sa.ForeignKeyConstraint(
            ["changed_by_id"],
            ["users.id"],
            name=op.f("fk_collection_task_status_history_changed_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["collection_task_id"],
            ["collection_tasks.id"],
            name=op.f("fk_collection_task_status_history_collection_task_id_collection_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collection_task_status_history")),
    )
    op.create_index(
        op.f("ix_collection_task_status_history_changed_by_id"),
        "collection_task_status_history",
        ["changed_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collection_task_status_history_collection_task_id"),
        "collection_task_status_history",
        ["collection_task_id"],
        unique=False,
    )
    op.create_table(
        "community_incidents",
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("assigned_to_id", sa.UUID(), nullable=True),
        sa.Column("photo_media_asset_id", sa.UUID(), nullable=True),
        sa.Column(
            "incident_type",
            sa.Enum(
                "illegal_dumping",
                "overflowing_bin",
                "hazardous_waste",
                "missed_collection",
                "open_burning",
                "other",
                name="incidenttype",
                native_enum=False,
                length=25,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "acknowledged",
                "in_progress",
                "resolved",
                "dismissed",
                name="incidentstatus",
                native_enum=False,
                length=20,
            ),
            server_default="open",
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("address_text", sa.String(length=500), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
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
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.CheckConstraint(
            "(status IN ('resolved', 'dismissed')) = (resolved_at IS NOT NULL)",
            name=op.f("ck_community_incidents_resolution_timestamp_consistent"),
        ),
        sa.CheckConstraint(
            "incident_type IN ('illegal_dumping', 'overflowing_bin', 'hazardous_waste', 'missed_collection', 'open_burning', 'other')",
            name=op.f("ck_community_incidents_incident_type_valid"),
        ),
        sa.CheckConstraint(
            "status IN ('open', 'acknowledged', 'in_progress', 'resolved', 'dismissed')",
            name=op.f("ck_community_incidents_status_valid"),
        ),
        sa.CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)",
            name=op.f("ck_community_incidents_geo_point_complete"),
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name=op.f("ck_community_incidents_latitude_range")
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name=op.f("ck_community_incidents_longitude_range")
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_id"],
            ["users.id"],
            name=op.f("fk_community_incidents_assigned_to_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["photo_media_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_community_incidents_photo_media_asset_id_media_assets"),
        ),
        sa.ForeignKeyConstraint(
            ["reporter_id"], ["users.id"], name=op.f("fk_community_incidents_reporter_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_community_incidents")),
    )
    op.create_index(
        op.f("ix_community_incidents_assigned_to_id"),
        "community_incidents",
        ["assigned_to_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_community_incidents_incident_type"),
        "community_incidents",
        ["incident_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_community_incidents_photo_media_asset_id"),
        "community_incidents",
        ["photo_media_asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_community_incidents_reporter_id"),
        "community_incidents",
        ["reporter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_community_incidents_status"), "community_incidents", ["status"], unique=False
    )
    op.create_table(
        "recovery_records",
        sa.Column("facility_id", sa.UUID(), nullable=False),
        sa.Column("material_category_id", sa.UUID(), nullable=False),
        sa.Column("collection_task_id", sa.UUID(), nullable=True),
        sa.Column("evidence_media_asset_id", sa.UUID(), nullable=True),
        sa.Column(
            "recovery_method",
            sa.Enum(
                "recycled",
                "composted",
                "reused",
                "refurbished",
                "energy_recovered",
                name="recoverymethod",
                native_enum=False,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("input_weight_kg", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("recovered_weight_kg", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column(
            "verification_status",
            sa.Enum(
                "pending",
                "verified",
                "rejected",
                name="verificationstatus",
                native_enum=False,
                length=16,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("verified_by_id", sa.UUID(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
            "(verification_status = 'pending') = (verified_at IS NULL)",
            name=op.f("ck_recovery_records_verification_timestamp_consistent"),
        ),
        sa.CheckConstraint(
            "(verification_status = 'pending') = (verified_by_id IS NULL)",
            name=op.f("ck_recovery_records_verifier_consistent"),
        ),
        sa.CheckConstraint(
            "recovery_method IN ('recycled', 'composted', 'reused', 'refurbished', 'energy_recovered')",
            name=op.f("ck_recovery_records_recovery_method_valid"),
        ),
        sa.CheckConstraint(
            "verification_status IN ('pending', 'verified', 'rejected')",
            name=op.f("ck_recovery_records_verification_status_valid"),
        ),
        sa.CheckConstraint(
            "input_weight_kg > 0", name=op.f("ck_recovery_records_input_weight_positive")
        ),
        sa.CheckConstraint(
            "recovered_weight_kg >= 0 AND recovered_weight_kg <= input_weight_kg",
            name=op.f("ck_recovery_records_recovered_within_input"),
        ),
        sa.ForeignKeyConstraint(
            ["collection_task_id"],
            ["collection_tasks.id"],
            name=op.f("fk_recovery_records_collection_task_id_collection_tasks"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_recovery_records_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["evidence_media_asset_id"],
            ["media_assets.id"],
            name=op.f("fk_recovery_records_evidence_media_asset_id_media_assets"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"],
            ["facilities.id"],
            name=op.f("fk_recovery_records_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["material_category_id"],
            ["material_categories.id"],
            name=op.f("fk_recovery_records_material_category_id_material_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_id"], ["users.id"], name=op.f("fk_recovery_records_verified_by_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recovery_records")),
    )
    op.create_index(
        op.f("ix_recovery_records_collection_task_id"),
        "recovery_records",
        ["collection_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recovery_records_created_by_id"),
        "recovery_records",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recovery_records_evidence_media_asset_id"),
        "recovery_records",
        ["evidence_media_asset_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recovery_records_facility_id"), "recovery_records", ["facility_id"], unique=False
    )
    op.create_index(
        op.f("ix_recovery_records_material_category_id"),
        "recovery_records",
        ["material_category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recovery_records_processed_at"), "recovery_records", ["processed_at"], unique=False
    )
    op.create_index(
        op.f("ix_recovery_records_verification_status"),
        "recovery_records",
        ["verification_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recovery_records_verified_by_id"),
        "recovery_records",
        ["verified_by_id"],
        unique=False,
    )
    op.create_table(
        "route_stops",
        sa.Column("route_plan_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("collection_task_id", sa.UUID(), nullable=True),
        sa.Column("facility_id", sa.UUID(), nullable=True),
        sa.Column("planned_arrival_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_arrival_at", sa.DateTime(timezone=True), nullable=True),
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
            "num_nonnulls(collection_task_id, facility_id) = 1",
            name=op.f("ck_route_stops_exactly_one_target"),
        ),
        sa.CheckConstraint("sequence >= 1", name=op.f("ck_route_stops_sequence_positive")),
        sa.ForeignKeyConstraint(
            ["collection_task_id"],
            ["collection_tasks.id"],
            name=op.f("fk_route_stops_collection_task_id_collection_tasks"),
        ),
        sa.ForeignKeyConstraint(
            ["facility_id"], ["facilities.id"], name=op.f("fk_route_stops_facility_id_facilities")
        ),
        sa.ForeignKeyConstraint(
            ["route_plan_id"],
            ["route_plans.id"],
            name=op.f("fk_route_stops_route_plan_id_route_plans"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_route_stops")),
        sa.UniqueConstraint(
            "route_plan_id", "sequence", name="uq_route_stops_route_plan_id_sequence"
        ),
    )
    op.create_index(
        op.f("ix_route_stops_collection_task_id"),
        "route_stops",
        ["collection_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_route_stops_facility_id"), "route_stops", ["facility_id"], unique=False
    )
    op.create_index(
        op.f("ix_route_stops_route_plan_id"), "route_stops", ["route_plan_id"], unique=False
    )
    op.create_table(
        "material_passports",
        sa.Column("passport_code", sa.String(length=64), nullable=False),
        sa.Column("material_category_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "in_processing",
                "recovered",
                "retired",
                name="passportstatus",
                native_enum=False,
                length=21,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("weight_kg", sa.Numeric(precision=14, scale=3), nullable=False),
        sa.Column("origin_collection_task_id", sa.UUID(), nullable=True),
        sa.Column("recovery_record_id", sa.UUID(), nullable=True),
        sa.Column("current_facility_id", sa.UUID(), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
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
            "status IN ('active', 'in_processing', 'recovered', 'retired')",
            name=op.f("ck_material_passports_status_valid"),
        ),
        sa.CheckConstraint("weight_kg > 0", name=op.f("ck_material_passports_weight_positive")),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name=op.f("fk_material_passports_created_by_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["current_facility_id"],
            ["facilities.id"],
            name=op.f("fk_material_passports_current_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["material_category_id"],
            ["material_categories.id"],
            name=op.f("fk_material_passports_material_category_id_material_categories"),
        ),
        sa.ForeignKeyConstraint(
            ["origin_collection_task_id"],
            ["collection_tasks.id"],
            name=op.f("fk_material_passports_origin_collection_task_id_collection_tasks"),
        ),
        sa.ForeignKeyConstraint(
            ["recovery_record_id"],
            ["recovery_records.id"],
            name=op.f("fk_material_passports_recovery_record_id_recovery_records"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_material_passports")),
        sa.UniqueConstraint("passport_code", name=op.f("uq_material_passports_passport_code")),
    )
    op.create_index(
        op.f("ix_material_passports_created_by_id"),
        "material_passports",
        ["created_by_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_material_passports_current_facility_id"),
        "material_passports",
        ["current_facility_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_material_passports_material_category_id"),
        "material_passports",
        ["material_category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_material_passports_origin_collection_task_id"),
        "material_passports",
        ["origin_collection_task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_material_passports_recovery_record_id"),
        "material_passports",
        ["recovery_record_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_material_passports_status"), "material_passports", ["status"], unique=False
    )
    op.create_table(
        "custody_events",
        sa.Column("material_passport_id", sa.UUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "created",
                "collected",
                "transferred",
                "received",
                "processed",
                "verified",
                name="custodyeventtype",
                native_enum=False,
                length=19,
            ),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("from_facility_id", sa.UUID(), nullable=True),
        sa.Column("to_facility_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('created', 'collected', 'transferred', 'received', 'processed', 'verified')",
            name=op.f("ck_custody_events_event_type_valid"),
        ),
        sa.CheckConstraint("sequence >= 1", name=op.f("ck_custody_events_sequence_positive")),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], name=op.f("fk_custody_events_actor_id_users")
        ),
        sa.ForeignKeyConstraint(
            ["from_facility_id"],
            ["facilities.id"],
            name=op.f("fk_custody_events_from_facility_id_facilities"),
        ),
        sa.ForeignKeyConstraint(
            ["material_passport_id"],
            ["material_passports.id"],
            name=op.f("fk_custody_events_material_passport_id_material_passports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["to_facility_id"],
            ["facilities.id"],
            name=op.f("fk_custody_events_to_facility_id_facilities"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_custody_events")),
        sa.UniqueConstraint(
            "material_passport_id",
            "sequence",
            name="uq_custody_events_material_passport_id_sequence",
        ),
    )
    op.create_index(
        op.f("ix_custody_events_actor_id"), "custody_events", ["actor_id"], unique=False
    )
    op.create_index(
        op.f("ix_custody_events_from_facility_id"),
        "custody_events",
        ["from_facility_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custody_events_material_passport_id"),
        "custody_events",
        ["material_passport_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_custody_events_to_facility_id"), "custody_events", ["to_facility_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_custody_events_to_facility_id"), table_name="custody_events")
    op.drop_index(op.f("ix_custody_events_material_passport_id"), table_name="custody_events")
    op.drop_index(op.f("ix_custody_events_from_facility_id"), table_name="custody_events")
    op.drop_index(op.f("ix_custody_events_actor_id"), table_name="custody_events")
    op.drop_table("custody_events")
    op.drop_index(op.f("ix_material_passports_status"), table_name="material_passports")
    op.drop_index(op.f("ix_material_passports_recovery_record_id"), table_name="material_passports")
    op.drop_index(
        op.f("ix_material_passports_origin_collection_task_id"), table_name="material_passports"
    )
    op.drop_index(
        op.f("ix_material_passports_material_category_id"), table_name="material_passports"
    )
    op.drop_index(
        op.f("ix_material_passports_current_facility_id"), table_name="material_passports"
    )
    op.drop_index(op.f("ix_material_passports_created_by_id"), table_name="material_passports")
    op.drop_table("material_passports")
    op.drop_index(op.f("ix_route_stops_route_plan_id"), table_name="route_stops")
    op.drop_index(op.f("ix_route_stops_facility_id"), table_name="route_stops")
    op.drop_index(op.f("ix_route_stops_collection_task_id"), table_name="route_stops")
    op.drop_table("route_stops")
    op.drop_index(op.f("ix_recovery_records_verified_by_id"), table_name="recovery_records")
    op.drop_index(op.f("ix_recovery_records_verification_status"), table_name="recovery_records")
    op.drop_index(op.f("ix_recovery_records_processed_at"), table_name="recovery_records")
    op.drop_index(op.f("ix_recovery_records_material_category_id"), table_name="recovery_records")
    op.drop_index(op.f("ix_recovery_records_facility_id"), table_name="recovery_records")
    op.drop_index(
        op.f("ix_recovery_records_evidence_media_asset_id"), table_name="recovery_records"
    )
    op.drop_index(op.f("ix_recovery_records_created_by_id"), table_name="recovery_records")
    op.drop_index(op.f("ix_recovery_records_collection_task_id"), table_name="recovery_records")
    op.drop_table("recovery_records")
    op.drop_index(op.f("ix_community_incidents_status"), table_name="community_incidents")
    op.drop_index(op.f("ix_community_incidents_reporter_id"), table_name="community_incidents")
    op.drop_index(
        op.f("ix_community_incidents_photo_media_asset_id"), table_name="community_incidents"
    )
    op.drop_index(op.f("ix_community_incidents_incident_type"), table_name="community_incidents")
    op.drop_index(op.f("ix_community_incidents_assigned_to_id"), table_name="community_incidents")
    op.drop_table("community_incidents")
    op.drop_index(
        op.f("ix_collection_task_status_history_collection_task_id"),
        table_name="collection_task_status_history",
    )
    op.drop_index(
        op.f("ix_collection_task_status_history_changed_by_id"),
        table_name="collection_task_status_history",
    )
    op.drop_table("collection_task_status_history")
    op.drop_index(op.f("ix_collection_events_recorded_by_id"), table_name="collection_events")
    op.drop_index(op.f("ix_collection_events_occurred_at"), table_name="collection_events")
    op.drop_index(op.f("ix_collection_events_facility_id"), table_name="collection_events")
    op.drop_index(op.f("ix_collection_events_collection_task_id"), table_name="collection_events")
    op.drop_table("collection_events")
    op.drop_index(
        "uq_collection_assignments_active_task",
        table_name="collection_assignments",
        postgresql_where=sa.text("unassigned_at IS NULL"),
    )
    op.drop_index(op.f("ix_collection_assignments_vehicle_id"), table_name="collection_assignments")
    op.drop_index(
        op.f("ix_collection_assignments_collection_task_id"), table_name="collection_assignments"
    )
    op.drop_index(
        op.f("ix_collection_assignments_assignee_id"), table_name="collection_assignments"
    )
    op.drop_index(
        op.f("ix_collection_assignments_assigned_by_id"), table_name="collection_assignments"
    )
    op.drop_table("collection_assignments")
    op.drop_index(
        op.f("ix_classification_predictions_reviewed_material_category_id"),
        table_name="classification_predictions",
    )
    op.drop_index(
        op.f("ix_classification_predictions_reviewed_by_id"),
        table_name="classification_predictions",
    )
    op.drop_index(
        op.f("ix_classification_predictions_review_status"), table_name="classification_predictions"
    )
    op.drop_index(
        op.f("ix_classification_predictions_model_version_id"),
        table_name="classification_predictions",
    )
    op.drop_index(
        op.f("ix_classification_predictions_media_asset_id"),
        table_name="classification_predictions",
    )
    op.drop_index(
        op.f("ix_classification_predictions_material_category_id"),
        table_name="classification_predictions",
    )
    op.drop_table("classification_predictions")
    op.drop_index(op.f("ix_route_plans_vehicle_id"), table_name="route_plans")
    op.drop_index(op.f("ix_route_plans_status"), table_name="route_plans")
    op.drop_index(op.f("ix_route_plans_start_facility_id"), table_name="route_plans")
    op.drop_index(op.f("ix_route_plans_planned_date"), table_name="route_plans")
    op.drop_index(op.f("ix_route_plans_end_facility_id"), table_name="route_plans")
    op.drop_index(op.f("ix_route_plans_driver_id"), table_name="route_plans")
    op.drop_index(op.f("ix_route_plans_created_by_id"), table_name="route_plans")
    op.drop_table("route_plans")
    op.drop_index(op.f("ix_media_assets_waste_report_id"), table_name="media_assets")
    op.drop_index(op.f("ix_media_assets_uploaded_by_id"), table_name="media_assets")
    op.drop_index(op.f("ix_media_assets_sha256"), table_name="media_assets")
    op.drop_table("media_assets")
    op.drop_index(op.f("ix_collection_tasks_waste_report_id"), table_name="collection_tasks")
    op.drop_index(op.f("ix_collection_tasks_status"), table_name="collection_tasks")
    op.drop_index(op.f("ix_collection_tasks_due_at"), table_name="collection_tasks")
    op.drop_index(
        op.f("ix_collection_tasks_destination_facility_id"), table_name="collection_tasks"
    )
    op.drop_index(op.f("ix_collection_tasks_created_by_id"), table_name="collection_tasks")
    op.drop_table("collection_tasks")
    op.drop_index(op.f("ix_waste_reports_status"), table_name="waste_reports")
    op.drop_index(op.f("ix_waste_reports_reporter_id"), table_name="waste_reports")
    op.drop_index(op.f("ix_waste_reports_reported_at"), table_name="waste_reports")
    op.drop_table("waste_reports")
    op.drop_index(op.f("ix_user_roles_role_id"), table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_index(op.f("ix_sorting_guidance_material_category_id"), table_name="sorting_guidance")
    op.drop_table("sorting_guidance")
    op.drop_index(op.f("ix_role_permissions_permission_id"), table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_index(
        "uq_reward_ledger_entries_idempotency",
        table_name="reward_ledger_entries",
        postgresql_where=sa.text("source_id IS NOT NULL AND entry_type = 'earned'"),
    )
    op.drop_index(op.f("ix_reward_ledger_entries_user_id"), table_name="reward_ledger_entries")
    op.drop_index(
        op.f("ix_reward_ledger_entries_reverses_entry_id"), table_name="reward_ledger_entries"
    )
    op.drop_index(
        op.f("ix_reward_ledger_entries_created_by_id"), table_name="reward_ledger_entries"
    )
    op.drop_table("reward_ledger_entries")
    op.drop_index("ix_notifications_recipient_id_read_at", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_forecast_results_metric_period_start", table_name="forecast_results")
    op.drop_index(op.f("ix_forecast_results_material_category_id"), table_name="forecast_results")
    op.drop_index(op.f("ix_forecast_results_facility_id"), table_name="forecast_results")
    op.drop_table("forecast_results")
    op.drop_index(op.f("ix_fleet_vehicles_status"), table_name="fleet_vehicles")
    op.drop_index(op.f("ix_fleet_vehicles_home_facility_id"), table_name="fleet_vehicles")
    op.drop_table("fleet_vehicles")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_family_id"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index("ix_audit_logs_occurred_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_entity_type_entity_id", table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_anomaly_alerts_status"), table_name="anomaly_alerts")
    op.drop_index(op.f("ix_anomaly_alerts_metric"), table_name="anomaly_alerts")
    op.drop_index(op.f("ix_anomaly_alerts_material_category_id"), table_name="anomaly_alerts")
    op.drop_index(op.f("ix_anomaly_alerts_facility_id"), table_name="anomaly_alerts")
    op.drop_index(op.f("ix_anomaly_alerts_detected_at"), table_name="anomaly_alerts")
    op.drop_index(op.f("ix_anomaly_alerts_acknowledged_by_id"), table_name="anomaly_alerts")
    op.drop_table("anomaly_alerts")
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_table("roles")
    op.drop_table("permissions")
    op.drop_table("material_categories")
    op.drop_index(op.f("ix_facilities_facility_type"), table_name="facilities")
    op.drop_table("facilities")
    op.drop_table("classification_model_versions")
