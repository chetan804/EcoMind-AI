"""Test bootstrap: isolated PostgreSQL database per session, real migrations.

- CI with a Postgres service: set ECOMIND_TEST_DATABASE_URL.
- Local/dev: reuses the bundled pgserver instance (or boots it) and creates a
  fresh ``ecomind_test_*`` database for the session.
"""

from __future__ import annotations

import os
import uuid

# Environment must be configured BEFORE importing the app.
os.environ.setdefault("ECOMIND_ENVIRONMENT", "test")
os.environ.setdefault("ECOMIND_RUN_EMBEDDED_WORKER", "false")
os.environ.setdefault("ECOMIND_RATE_LIMIT_AUTH", "10000")
os.environ.setdefault("ECOMIND_RATE_LIMIT_WRITE", "10000")
os.environ.setdefault("ECOMIND_RATE_LIMIT_AI", "10000")
os.environ.setdefault("ECOMIND_RATE_LIMIT_UPLOAD", "10000")
os.environ.setdefault("ECOMIND_RATE_LIMIT_TELEMETRY", "100000")
os.environ.setdefault("ECOMIND_RATE_LIMIT_READ", "100000")

import asyncio  # noqa: E402
import contextlib  # noqa: E402

_PG_HANDLE = None
_TEST_DB = None


def _prepare_database() -> str:
    global _PG_HANDLE, _TEST_DB
    if os.environ.get("ECOMIND_TEST_DATABASE_URL"):
        return os.environ["ECOMIND_TEST_DATABASE_URL"]
    import pgserver

    _PG_HANDLE = pgserver.get_server("/home/user/EcoMind-AI/.pgdata", cleanup_mode=None)
    _TEST_DB = f"ecomind_test_{uuid.uuid4().hex[:8]}"
    _PG_HANDLE.psql(f"CREATE DATABASE {_TEST_DB};")
    base = _PG_HANDLE.get_uri()  # postgresql://postgres:@/postgres?host=...
    return f"postgresql+asyncpg://postgres@/{_TEST_DB}{base[base.index('?'):]}"


DATABASE_URL = _prepare_database()
os.environ["ECOMIND_DATABASE_URL"] = DATABASE_URL


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("/home/user/EcoMind-AI/backend/alembic.ini")
    cfg.set_main_option("script_location", "/home/user/EcoMind-AI/backend/alembic")
    os.environ["ECOMIND_DATABASE_URL"] = DATABASE_URL
    from app.core.config import get_settings

    get_settings.cache_clear()
    command.upgrade(cfg, "head")


_run_migrations()

import httpx  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport  # noqa: E402


@pytest.fixture(scope="session")
def event_loop_policy():
    return asyncio.get_event_loop_policy()


@pytest.fixture(scope="session")
async def app():
    from app.main import app as fastapi_app

    # Seed RBAC once for the session.
    from app.auth.rbac import seed_rbac
    from app.core.db import SessionLocal

    async with SessionLocal() as session:
        await seed_rbac(session)
    yield fastapi_app


@pytest.fixture(scope="session")
async def client(app):
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Helpers -----------------------------------------------------------------


async def api(client, method: str, path: str, token: str | None = None, org_id=None, **kwargs):
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if org_id:
        headers["X-Org-Id"] = str(org_id)
    return await client.request(method, path, headers=headers, **kwargs)


async def register_user(client, email: str | None = None, password: str = "Password123!x") -> dict:
    email = email or f"u{uuid.uuid4().hex[:10]}@test.ecomind"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": f"User {email[:4]}"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def create_org(client, token: str, name: str | None = None) -> dict:
    slug = f"org-{uuid.uuid4().hex[:10]}"
    r = await client.post(
        "/api/v1/organizations",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": name or slug, "slug": slug, "org_type": "municipality"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def make_org_with_admin(client) -> tuple[dict, str]:
    """Returns (org, admin_token)."""
    user = await register_user(client)
    org = await create_org(client, user["tokens"]["access_token"])
    return org, user["tokens"]["access_token"]


async def add_member(client, admin_token: str, org_id, role: str = "citizen") -> tuple[dict, str]:
    """Invite + accept via API, returning (user, access_token)."""
    user = await register_user(client)
    invite_r = await api(
        client, "POST", "/api/v1/organizations/current/invitations", admin_token, org_id,
        json={"email": user["user"]["email"], "role_code": role},
    )
    assert invite_r.status_code == 201, invite_r.text
    token = invite_r.json()["invite_token"]
    accept_r = await api(
        client, "POST", "/api/v1/organizations/invitations/accept", user["tokens"]["access_token"],
        json={"token": token},
    )
    assert accept_r.status_code == 200, accept_r.text
    return user["user"], user["tokens"]["access_token"]


async def create_zone(client, admin_token, org_id) -> dict:
    """Creates a small service-area zone around (12.94, 77.60)."""
    ring = [
        [77.58, 12.92], [77.63, 12.92], [77.63, 12.97], [77.58, 12.97], [77.58, 12.92],
    ]
    r = await api(
        client, "POST", "/api/v1/organizations/current/zones", admin_token, org_id,
        json={
            "name": f"Zone {uuid.uuid4().hex[:4]}",
            "code": f"Z{uuid.uuid4().hex[:4].upper()}",
            "boundary": {"type": "Polygon", "coordinates": [ring]},
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def create_point(client, admin_token, org_id, lat: float, lng: float) -> dict:
    r = await api(
        client, "POST", "/api/v1/collection/points", admin_token, org_id,
        json={
            "code": f"CP{uuid.uuid4().hex[:6].upper()}",
            "name": f"Point {uuid.uuid4().hex[:4]}",
            "latitude": lat,
            "longitude": lng,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()
