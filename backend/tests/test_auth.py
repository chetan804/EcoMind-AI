"""Authentication and authorization tests."""

from __future__ import annotations

import uuid

from conftest import add_member, api, make_org_with_admin, register_user


async def test_register_login_flow(client):
    email = f"auth{uuid.uuid4().hex[:8]}@test.ecomind"
    user = await register_user(client, email=email)
    assert user["user"]["email"] == email
    assert "access_token" in user["tokens"]

    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Password123!x"}
    )
    assert r.status_code == 200
    assert r.json()["tokens"]["access_token"]


async def test_login_wrong_password(client):
    user = await register_user(client)
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": user["user"]["email"], "password": "wrong-password"},
    )
    assert r.status_code == 401


async def test_duplicate_registration_rejected(client):
    user = await register_user(client)
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": user["user"]["email"], "password": "Password123!x", "full_name": "Dup"},
    )
    assert r.status_code == 409


async def test_refresh_rotation_and_reuse_detection(client):
    user = await register_user(client)
    refresh = user["tokens"]["refresh_token"]

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200, r.text
    new_pair = r.json()
    assert new_pair["refresh_token"] != refresh

    # Replaying the OLD token must fail and revoke the whole family.
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401

    # The rotated token is now dead too (family revoked).
    r3 = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_pair["refresh_token"]})
    assert r3.status_code == 401


async def test_logout_revokes_refresh(client):
    user = await register_user(client)
    refresh = user["tokens"]["refresh_token"]
    r = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert r.status_code == 200
    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r2.status_code == 401


async def test_invalid_token_rejected(client):
    r = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer garbage.token.here"})
    assert r.status_code == 401
    r2 = await client.get("/api/v1/auth/me")
    assert r2.status_code == 401


async def test_me_requires_auth(client):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401


async def test_password_reset_flow(client):
    user = await register_user(client)
    r = await client.post(
        "/api/v1/auth/forgot-password", json={"email": user["user"]["email"]}
    )
    assert r.status_code == 200
    # Token is not exposed via API (logged server-side); test the reset path via service
    from app.core.db import SessionLocal
    from app.core.security import hash_token, new_opaque_token
    from app.auth.models import PasswordResetToken, User
    from sqlalchemy import select
    from datetime import timedelta
    from app.core.db import utcnow

    token = new_opaque_token("empr")
    async with SessionLocal() as session:
        db_user = (
            await session.execute(select(User).where(User.email == user["user"]["email"]))
        ).scalar_one()
        session.add(
            PasswordResetToken(
                user_id=db_user.id, token_hash=hash_token(token),
                expires_at=utcnow() + timedelta(minutes=30), created_at=utcnow(),
            )
        )
        await session.commit()

    r2 = await client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewSecure123!x"},
    )
    assert r2.status_code == 200
    r3 = await client.post(
        "/api/v1/auth/login", json={"email": user["user"]["email"], "password": "NewSecure123!x"}
    )
    assert r3.status_code == 200


async def test_permission_enforcement_by_role(client):
    """Citizen cannot manage fleet; collector cannot invite users; ops manager can."""
    org, admin_token = await make_org_with_admin(client)

    citizen, citizen_token = await add_member(client, admin_token, org["id"], role="citizen")
    r = await api(client, "POST", "/api/v1/fleet/vehicles", citizen_token, org["id"],
                  json={"code": "V-X"})
    assert r.status_code == 403

    collector, collector_token = await add_member(client, admin_token, org["id"], role="collector")
    r = await api(client, "POST", "/api/v1/organizations/current/invitations", collector_token, org["id"],
                  json={"email": "x@y.z", "role_code": "citizen"})
    assert r.status_code == 403

    ops, ops_token = await add_member(client, admin_token, org["id"], role="ops_manager")
    r = await api(client, "GET", "/api/v1/fleet/vehicles", ops_token, org["id"])
    assert r.status_code == 200


async def test_role_change_takes_effect(client):
    org, admin_token = await make_org_with_admin(client)
    member, member_token = await add_member(client, admin_token, org["id"], role="citizen")

    r = await api(client, "GET", "/api/v1/fleet/vehicles", member_token, org["id"])
    assert r.status_code == 403

    promote = await api(
        client, "PATCH", f"/api/v1/organizations/current/members/{member['id']}", admin_token, org["id"],
        json={"role_code": "ops_manager"},
    )
    assert promote.status_code == 200

    r2 = await api(client, "GET", "/api/v1/fleet/vehicles", member_token, org["id"])
    assert r2.status_code == 200


async def test_deactivated_member_loses_access(client):
    org, admin_token = await make_org_with_admin(client)
    member, member_token = await add_member(client, admin_token, org["id"], role="ops_manager")

    r = await api(
        client, "PATCH", f"/api/v1/organizations/current/members/{member['id']}", admin_token, org["id"],
        json={"is_active": False},
    )
    assert r.status_code == 200
    r2 = await api(client, "GET", "/api/v1/fleet/vehicles", member_token, org["id"])
    assert r2.status_code == 403
