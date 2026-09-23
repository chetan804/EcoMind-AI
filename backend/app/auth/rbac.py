"""Permission catalogue and role bundles.

Authorization is by permission code, never by role name. Roles are seed data;
platform admins get all permissions via a runtime flag, not a seeded role.
"""

from __future__ import annotations

PERMISSIONS: dict[str, tuple[str, str]] = {
    # code: (description, category)
    "platform:admin": ("Platform-level administration across organizations", "platform"),
    "org:read": ("View organization profile", "org"),
    "org:update": ("Update organization settings and branding", "org"),
    "unit:manage": ("Create and manage operational units", "org"),
    "zone:manage": ("Create and manage service-area zones", "org"),
    "category:manage": ("Configure waste categories", "org"),
    "user:read": ("List organization members", "org"),
    "user:invite": ("Invite members and assign roles", "org"),
    "user:manage": ("Deactivate members and change roles", "org"),
    "audit:read": ("Read the organization audit log", "org"),
    "report:create": ("Submit waste reports", "waste"),
    "report:read": ("View own waste reports", "waste"),
    "report:read_all": ("View all organization waste reports", "waste"),
    "report:triage": ("Classify, prioritize and re-open reports", "waste"),
    "report:assign": ("Assign reports to staff", "waste"),
    "report:resolve": ("Resolve and close reports", "waste"),
    "complaint:create": ("File complaints", "complaints"),
    "complaint:read": ("View own complaints", "complaints"),
    "complaint:read_all": ("View all organization complaints", "complaints"),
    "complaint:triage": ("Classify and prioritize complaints", "complaints"),
    "complaint:assign": ("Assign complaints", "complaints"),
    "complaint:comment": ("Comment on complaints (staff-visible internal notes)", "complaints"),
    "complaint:resolve": ("Resolve and close complaints", "complaints"),
    "collection:read": ("View collection points, schedules and events", "collection"),
    "collection:manage": ("Create and manage collection points and schedules", "collection"),
    "collection:complete": ("Record collection completions and weights", "collection"),
    "fleet:read": ("View fleet", "fleet"),
    "fleet:manage": ("Manage vehicles and driver profiles", "fleet"),
    "route:read": ("View routes", "routing"),
    "route:generate": ("Generate optimized routes", "routing"),
    "route:assign": ("Assign vehicles and drivers to routes", "routing"),
    "route:execute": ("Execute routes in the field (stops, skips, weights)", "routing"),
    "device:read": ("View IoT devices and telemetry", "iot"),
    "device:manage": ("Register, key-rotate and revoke devices", "iot"),
    "alert:read": ("View alerts", "iot"),
    "alert:manage": ("Acknowledge, resolve and configure alerts", "iot"),
    "ai:read": ("View AI inferences", "ai"),
    "ai:review": ("Review and correct AI outputs", "ai"),
    "sustainability:read": ("View sustainability metrics and methodology", "sustainability"),
    "sustainability:recompute": ("Recompute sustainability records", "sustainability"),
    "analytics:read": ("View operational and executive analytics", "analytics"),
    "notification:read": ("Read own notifications", "notifications"),
    "media:upload": ("Upload images and documents", "media"),
}

ROLES: dict[str, dict] = {
    "org_admin": {
        "name": "Organization Admin",
        "description": "Full administration of one organization",
        "sort_order": 10,
        "permissions": [c for c in PERMISSIONS if not c.startswith("platform:")],
    },
    "ops_manager": {
        "name": "Operations Manager",
        "description": "Runs day-to-day collection operations",
        "sort_order": 20,
        "permissions": [
            "org:read", "unit:manage", "zone:manage", "category:manage", "user:read", "audit:read",
            "report:read_all", "report:triage", "report:assign", "report:resolve",
            "complaint:read_all", "complaint:triage", "complaint:assign", "complaint:comment",
            "complaint:resolve",
            "collection:read", "collection:manage", "collection:complete",
            "fleet:read", "fleet:manage",
            "route:read", "route:generate", "route:assign",
            "device:read", "device:manage", "alert:read", "alert:manage",
            "ai:read", "ai:review",
            "sustainability:read", "sustainability:recompute",
            "analytics:read", "notification:read", "media:upload",
        ],
    },
    "field_supervisor": {
        "name": "Field Supervisor",
        "description": "Supervises field crews and dispatch",
        "sort_order": 30,
        "permissions": [
            "org:read", "user:read",
            "report:read_all", "report:triage", "report:assign",
            "complaint:read_all", "complaint:assign", "complaint:comment",
            "collection:read", "collection:manage", "collection:complete",
            "fleet:read",
            "route:read", "route:generate", "route:assign", "route:execute",
            "device:read", "alert:read", "alert:manage",
            "ai:read", "analytics:read", "notification:read", "media:upload",
        ],
    },
    "collector": {
        "name": "Collector / Driver",
        "description": "Executes collection routes in the field",
        "sort_order": 40,
        "permissions": [
            "org:read",
            "report:read_all", "complaint:read_all",
            "collection:read", "collection:complete",
            "route:read", "route:execute",
            "alert:read", "notification:read", "media:upload",
        ],
    },
    "sustainability_analyst": {
        "name": "Sustainability Analyst",
        "description": "Analyses environmental performance and methodology",
        "sort_order": 50,
        "permissions": [
            "org:read", "audit:read",
            "report:read_all", "complaint:read_all",
            "collection:read", "fleet:read", "route:read",
            "device:read", "alert:read", "ai:read",
            "sustainability:read", "sustainability:recompute", "analytics:read",
            "notification:read",
        ],
    },
    "citizen": {
        "name": "Citizen",
        "description": "Reports waste, tracks issues, participates in sustainability",
        "sort_order": 60,
        "permissions": [
            "org:read", "report:create", "report:read", "complaint:create", "complaint:read",
            "sustainability:read", "notification:read", "media:upload",
        ],
    },
    "viewer": {
        "name": "Viewer",
        "description": "Read-only visibility into operations",
        "sort_order": 70,
        "permissions": [
            "org:read", "report:read_all", "complaint:read_all",
            "collection:read", "fleet:read", "route:read",
            "device:read", "alert:read", "sustainability:read", "analytics:read",
            "notification:read",
        ],
    },
}


async def seed_rbac(session) -> None:
    """Idempotently seed permissions, roles and role→permission links."""
    from sqlalchemy import insert, select

    from app.auth.models import Permission, Role, role_permissions

    for code, (description, category) in PERMISSIONS.items():
        exists = (
            await session.execute(select(Permission).where(Permission.code == code))
        ).scalar_one_or_none()
        if not exists:
            session.add(Permission(code=code, description=description, category=category))
    await session.flush()

    for role_code, spec in ROLES.items():
        role = (
            await session.execute(select(Role).where(Role.code == role_code))
        ).scalar_one_or_none()
        if not role:
            role = Role(
                code=role_code,
                name=spec["name"],
                description=spec["description"],
                is_system=True,
                sort_order=spec["sort_order"],
            )
            session.add(role)
            await session.flush()
        existing = {
            row[0]
            for row in (
                await session.execute(
                    select(role_permissions.c.permission_code).where(
                        role_permissions.c.role_code == role_code
                    )
                )
            ).all()
        }
        for perm in spec["permissions"]:
            if perm not in existing:
                await session.execute(
                    insert(role_permissions).values(role_code=role_code, permission_code=perm)
                )
    await session.commit()
