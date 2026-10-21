"""Role and permission catalog: the single source of truth for authorization data.

Permissions are ``<resource>:<action>`` strings (``core/permissions.py``). Roles are bundles of
permissions. The database copy is seeded by migration ``0002`` from a frozen snapshot of this
catalog; ``tests/integration/test_rbac_seed.py`` fails if the two drift apart. To add or change a
grant, edit this file and add a *new* migration - never edit an applied one.

Deny by default: a user can do only what one of their roles grants. Self-registration always
yields ``citizen``; every other role is assigned by an administrator.
"""

from __future__ import annotations

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
    "fleet:track": "Report positions of the vehicle the user is currently assigned to",
    "fleet:simulate": "Write labelled simulator positions (demonstration environments only)",
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
    "rewards:redeem": "Spend reward points on catalogue items",
    "notifications:read_own": "View the user's notifications",
    "forecasting:read": "View fill-level and volume forecasts",
    "forecasting:run": "Run forecasting jobs",
    "anomalies:read": "View anomaly alerts",
    "anomalies:manage": "Acknowledge and resolve anomaly alerts",
    "analytics:read": "View dashboards and analytics",
    "users:read": "View user accounts and roles",
    "users:manage": "Create, deactivate and change roles of users",
    "marketplace:read": "Browse surplus-material listings",
    "marketplace:request": "Ask for a surplus-material listing",
    "marketplace:create": "Offer surplus material in the marketplace",
    "marketplace:manage": "Moderate and act on any marketplace listing",
    "audit:read": "View the audit log",
    "settings:manage": "Change system and security settings",
}

_CITIZEN = {
    "waste_reports:create",
    "waste_reports:read_own",
    "classification:predict",
    "sorting_guide:read",
    "facilities:read",
    "incidents:create",
    "incidents:read_own",
    "rewards:read_own",
    "rewards:redeem",
    "notifications:read_own",
    "marketplace:read",
    "marketplace:request",
}

_COLLECTOR = {
    "fleet:track",
    "waste_reports:read_all",
    "classification:predict",
    "collection:read",
    "collection:execute",
    "routes:read",
    "fleet:read",
    "facilities:read",
    "sorting_guide:read",
    "incidents:create",
    "notifications:read_own",
    "marketplace:read",
    "marketplace:request",
}

_FACILITY_OPERATOR = {
    "waste_reports:read_all",
    "classification:predict",
    "classification:review",
    "collection:read",
    "facilities:read",
    "sorting_guide:read",
    "circular_economy:read",
    "circular_economy:manage",
    "passports:read",
    "passports:manage",
    "notifications:read_own",
    "marketplace:read",
    "marketplace:request",
    "marketplace:create",
}

_MANAGER = _FACILITY_OPERATOR | {
    "waste_reports:review",
    "collection:manage",
    "facilities:manage",
    "fleet:read",
    "fleet:manage",
    "fleet:simulate",
    "routes:read",
    "routes:manage",
    "sorting_guide:manage",
    "circular_economy:verify",
    "incidents:triage",
    "rewards:manage",
    "forecasting:read",
    "forecasting:run",
    "anomalies:read",
    "anomalies:manage",
    "analytics:read",
    "users:read",
    "marketplace:manage",
}

ROLES: dict[str, tuple[str, frozenset[str]]] = {
    "citizen": ("Resident who reports waste and learns how to sort it", frozenset(_CITIZEN)),
    "collector": ("Field collector or driver working assigned tasks", frozenset(_COLLECTOR)),
    "facility_operator": (
        "Processing facility staff recording recovery and custody",
        frozenset(_FACILITY_OPERATOR),
    ),
    "manager": ("Operations manager planning and overseeing collection", frozenset(_MANAGER)),
    "administrator": ("Full access including users, audit and settings", frozenset(PERMISSIONS)),
}

DEFAULT_REGISTRATION_ROLE = "citizen"


def _validate() -> None:
    for role, (_, grants) in ROLES.items():
        unknown = grants - PERMISSIONS.keys()
        if unknown:
            raise RuntimeError(f"role {role!r} grants unknown permissions: {sorted(unknown)}")
    if DEFAULT_REGISTRATION_ROLE not in ROLES:
        raise RuntimeError("DEFAULT_REGISTRATION_ROLE is not a defined role")


_validate()
