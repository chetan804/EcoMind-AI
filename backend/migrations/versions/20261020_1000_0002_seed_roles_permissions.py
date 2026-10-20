"""Seed system roles, permissions and their grants.

Revision ID: 0002
Revises: 0001

This is a frozen snapshot of ``app/modules/users/rbac.py`` at the time it was written. It is
deliberately literal (no imports from application code) so that later catalog edits cannot change
what this revision does. Later grants belong in a new revision.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS: dict[str, str] = {
    "waste_reports:create": "Submit a waste report",
    "waste_reports:read_own": "View waste reports the user submitted",
    "waste_reports:read_all": "View every waste report",
    "waste_reports:review": "Verify or reject waste reports",
    "classification:predict": "Run waste classification on an image",
    "classification:review": "Confirm or correct classification predictions",
    "classification:manage_models": "Register and activate classification model versions",
    "collection:read": "View collection tasks",
    "collection:manage": "Create, assign and cancel collection tasks",
    "collection:execute": "Work on collection tasks assigned to the user",
    "facilities:read": "View facilities and depots",
    "facilities:manage": "Create and edit facilities and depots",
    "fleet:read": "View fleet vehicles",
    "fleet:manage": "Create and edit fleet vehicles",
    "routes:read": "View route plans",
    "routes:manage": "Generate and edit route plans",
    "sorting_guide:read": "Read the material sorting guide",
    "sorting_guide:manage": "Edit materials and sorting guidance",
    "circular_economy:read": "View recovery records",
    "circular_economy:manage": "Create and edit recovery records",
    "circular_economy:verify": "Verify recovery records",
    "passports:read": "View material passports and custody history",
    "passports:manage": "Create passports and record custody events",
    "incidents:create": "Report a community incident",
    "incidents:read_own": "View incidents the user reported",
    "incidents:triage": "View, assign and resolve all incidents",
    "rewards:read_own": "View the user's own rewards ledger",
    "rewards:manage": "Adjust rewards and review the full ledger",
    "notifications:read_own": "View the user's notifications",
    "forecasting:read": "View fill-level and volume forecasts",
    "forecasting:run": "Run forecasting jobs",
    "anomalies:read": "View anomaly alerts",
    "anomalies:manage": "Acknowledge and resolve anomaly alerts",
    "analytics:read": "View dashboards and analytics",
    "users:read": "View user accounts and roles",
    "users:manage": "Create, deactivate and change roles of users",
    "audit:read": "View the audit log",
    "settings:manage": "Change system and security settings",
}

ROLES: dict[str, tuple[str, list[str]]] = {
    "citizen": (
        "Resident who reports waste and learns how to sort it",
        [
            "classification:predict",
            "facilities:read",
            "incidents:create",
            "incidents:read_own",
            "notifications:read_own",
            "rewards:read_own",
            "sorting_guide:read",
            "waste_reports:create",
            "waste_reports:read_own",
        ],
    ),
    "collector": (
        "Field collector or driver working assigned tasks",
        [
            "classification:predict",
            "collection:execute",
            "collection:read",
            "facilities:read",
            "fleet:read",
            "incidents:create",
            "notifications:read_own",
            "routes:read",
            "sorting_guide:read",
            "waste_reports:read_all",
        ],
    ),
    "facility_operator": (
        "Processing facility staff recording recovery and custody",
        [
            "circular_economy:manage",
            "circular_economy:read",
            "classification:predict",
            "classification:review",
            "collection:read",
            "facilities:read",
            "notifications:read_own",
            "passports:manage",
            "passports:read",
            "sorting_guide:read",
            "waste_reports:read_all",
        ],
    ),
    "manager": (
        "Operations manager planning and overseeing collection",
        [
            "analytics:read",
            "anomalies:manage",
            "anomalies:read",
            "circular_economy:manage",
            "circular_economy:read",
            "circular_economy:verify",
            "classification:predict",
            "classification:review",
            "collection:manage",
            "collection:read",
            "facilities:manage",
            "facilities:read",
            "fleet:manage",
            "fleet:read",
            "forecasting:read",
            "forecasting:run",
            "incidents:triage",
            "notifications:read_own",
            "passports:manage",
            "passports:read",
            "rewards:manage",
            "routes:manage",
            "routes:read",
            "sorting_guide:manage",
            "sorting_guide:read",
            "users:read",
            "waste_reports:read_all",
            "waste_reports:review",
        ],
    ),
    "administrator": (
        "Full access including users, audit and settings",
        [
            "analytics:read",
            "anomalies:manage",
            "anomalies:read",
            "audit:read",
            "circular_economy:manage",
            "circular_economy:read",
            "circular_economy:verify",
            "classification:manage_models",
            "classification:predict",
            "classification:review",
            "collection:execute",
            "collection:manage",
            "collection:read",
            "facilities:manage",
            "facilities:read",
            "fleet:manage",
            "fleet:read",
            "forecasting:read",
            "forecasting:run",
            "incidents:create",
            "incidents:read_own",
            "incidents:triage",
            "notifications:read_own",
            "passports:manage",
            "passports:read",
            "rewards:manage",
            "rewards:read_own",
            "routes:manage",
            "routes:read",
            "settings:manage",
            "sorting_guide:manage",
            "sorting_guide:read",
            "users:manage",
            "users:read",
            "waste_reports:create",
            "waste_reports:read_all",
            "waste_reports:read_own",
            "waste_reports:review",
        ],
    ),
}


def upgrade() -> None:
    conn = op.get_bind()
    for code, description in PERMISSIONS.items():
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, description) VALUES (:code, :description) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "description": description},
        )
    for name, (description, grants) in ROLES.items():
        conn.execute(
            sa.text(
                "INSERT INTO roles (name, description, is_system) VALUES (:name, :description, true) "
                "ON CONFLICT (name) DO NOTHING"
            ),
            {"name": name, "description": description},
        )
        for code in grants:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT r.id, p.id FROM roles r, permissions p "
                    "WHERE r.name = :name AND p.code = :code ON CONFLICT DO NOTHING"
                ),
                {"name": name, "code": code},
            )


def downgrade() -> None:
    # Removes only what this revision created. user_roles rows cascade with the roles.
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM roles WHERE name = ANY(:names)"), {"names": list(ROLES)})
    conn.execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"), {"codes": list(PERMISSIONS)}
    )
