"""The seeded roles/permissions must match the catalog in code (drift guard)."""

from __future__ import annotations

from sqlalchemy import Engine, text

from app.modules.users.rbac import DEFAULT_REGISTRATION_ROLE, PERMISSIONS, ROLES
from tests.fixtures.database import downgrade


def _grants(engine: Engine) -> dict[str, set[str]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT r.name, p.code FROM roles r "
                "JOIN role_permissions rp ON rp.role_id = r.id "
                "JOIN permissions p ON p.id = rp.permission_id"
            )
        ).all()
    grants: dict[str, set[str]] = {}
    for name, code in rows:
        grants.setdefault(name, set()).add(code)
    return grants


def test_migration_seeds_exactly_the_catalog(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        permissions = {c for (c,) in connection.execute(text("SELECT code FROM permissions"))}
        roles = {
            n: s for n, s in connection.execute(text("SELECT name, is_system FROM roles")).all()
        }
    assert permissions == set(PERMISSIONS)
    assert set(roles) == set(ROLES) and all(roles.values())
    assert _grants(migrated_engine) == {name: set(grants) for name, (_, grants) in ROLES.items()}


def test_least_privilege_shape_of_the_catalog() -> None:
    admin_only = {"users:manage", "audit:read", "settings:manage", "classification:manage_models"}
    for name, (_, grants) in ROLES.items():
        if name != "administrator":
            assert not (grants & admin_only), f"{name} must not hold admin-only permissions"
    assert ROLES["administrator"][1] == set(PERMISSIONS)
    assert DEFAULT_REGISTRATION_ROLE == "citizen"
    citizen = ROLES["citizen"][1]
    assert not any(
        code.endswith((":manage", ":read_all", ":triage", ":review")) for code in citizen
    )


def test_seed_migration_downgrades_cleanly(migrated_engine: Engine) -> None:
    downgrade(migrated_engine, "0001")
    with migrated_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM roles")).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM permissions")).scalar_one() == 0
