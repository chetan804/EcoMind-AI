"""A citizen, the only role public sign-up can produce, is refused every route it holds no permission for."""

from __future__ import annotations

import re
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import Engine

from app.common.route_inventory import inventory
from app.modules.users.rbac import ROLES
from tests.fixtures.api import CSRF, ClientFactory, bearer, create_user, login

CITIZEN_PERMISSIONS = ROLES["citizen"][1]


def _fill(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.UUID(int=1)), path)


def test_a_citizen_gets_403_on_every_route_whose_permissions_it_does_not_hold(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email="citizen@example.org", roles=("citizen",))
    headers = {**bearer(login(client, "citizen@example.org")["access_token"]), **CSRF}
    refused: list[str] = []
    for route in inventory(client.app):  # type: ignore[arg-type]
        if not route.permissions:
            continue
        held = set(route.permissions) & CITIZEN_PERMISSIONS
        allowed = bool(held) if route.any_of else held == set(route.permissions)
        if allowed:
            continue
        response = client.request(route.method, _fill(route.path), headers=headers, json={})
        assert response.status_code == 403, (route.method, route.path, response.status_code)
        refused.append(f"{route.method} {route.path}")
    # The guard is meaningful only if there are many such routes (administration, analytics, fleet...).
    assert len(refused) > 80


def test_an_administrator_route_is_refused_to_a_citizen_by_name(
    make_client: ClientFactory, db_engine: Engine
) -> None:
    client = make_client()
    create_user(db_engine, email="citizen@example.org", roles=("citizen",))
    headers = bearer(login(client, "citizen@example.org")["access_token"])
    for path in ("/api/v1/admin/users", "/api/v1/access-requests", "/api/v1/admin/audit-logs"):
        assert client.get(path, headers=headers).status_code == 403, path
    assert client.get("/api/v1/analytics/overview", headers=headers).status_code == 403
