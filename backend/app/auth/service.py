"""Authentication service: registration, login, token rotation, password reset."""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select, update

from app.auth.models import PasswordResetToken, RefreshToken, User
from app.auth.rbac import PERMISSIONS, ROLES
from app.core.config import settings
from app.core.db import AsyncSession, utcnow
from app.core.errors import AuthError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    hash_password,
    hash_token,
    new_opaque_token,
    verify_password,
)
from app.notifications.service import notify_user
from app.orgs.models import Organization, OrgMembership

log = get_logger("auth")


async def register(session: AsyncSession, *, email: str, password: str, full_name: str, phone: str | None) -> User:
    email = email.strip().lower()
    existing = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing:
        raise ConflictError("An account with this email already exists.")
    user = User(
        email=email,
        full_name=full_name.strip(),
        phone=phone,
        password_hash=hash_password(password),
    )
    session.add(user)
    await session.flush()
    await notify_user(
        session,
        user_id=user.id,
        organization_id=None,
        category="system",
        title="Welcome to EcoMind-AI",
        body="Your account is ready. Join an organization or create one to get started.",
    )
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    user = (
        await session.execute(select(User).where(User.email == email.strip().lower()))
    ).scalar_one_or_none()
    if user is None or user.password_hash is None:
        # Constant-ish work to blunt user-enumeration timing.
        verify_password(hash_password("timing-equalizer"), password)
        raise AuthError("Invalid email or password.")
    if not verify_password(user.password_hash, password):
        raise AuthError("Invalid email or password.")
    if not user.is_active:
        raise AuthError("This account has been deactivated.")
    user.last_login_at = utcnow()
    return user


async def issue_token_pair(
    session: AsyncSession, user: User, *, user_agent: str | None, ip: str | None
) -> tuple[str, str]:
    access = create_access_token(user.id, user.is_platform_admin)
    refresh = new_opaque_token("emr")
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            created_at=utcnow(),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_days),
            user_agent=(user_agent or "")[:255] or None,
            ip=ip,
        )
    )
    return access, refresh


async def rotate_refresh_token(
    session: AsyncSession, refresh_token: str, *, user_agent: str | None, ip: str | None
) -> tuple[User, str, str]:
    token_hash = hash_token(refresh_token)
    row = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    ).scalar_one_or_none()
    if row is None:
        raise AuthError("Unknown refresh token.")
    if row.revoked_at is not None:
        # Reuse of a rotated token is treated as theft: kill the whole family.
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.user_id == row.user_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=utcnow())
        )
        await session.commit()  # persist the revocation even though we abort the request
        log.warning("refresh_token_reuse", user_id=str(row.user_id), ip=ip)
        raise AuthError("Refresh token already used. All sessions were revoked — please log in again.")
    if row.expires_at < utcnow():
        raise AuthError("Refresh token expired.")

    user = (await session.execute(select(User).where(User.id == row.user_id))).scalar_one()
    if not user.is_active:
        raise AuthError("This account has been deactivated.")

    access, new_refresh = await issue_token_pair(session, user, user_agent=user_agent, ip=ip)
    row.revoked_at = utcnow()
    row.replaced_by_hash = hash_token(new_refresh)
    return user, access, new_refresh


async def revoke_refresh_token(session: AsyncSession, refresh_token: str) -> None:
    token_hash = hash_token(refresh_token)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == token_hash, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def revoke_all_user_tokens(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


# --- Password reset ---------------------------------------------------------


async def create_password_reset(session: AsyncSession, email: str) -> str | None:
    user = (
        await session.execute(select(User).where(User.email == email.strip().lower()))
    ).scalar_one_or_none()
    if user is None:
        return None  # do not reveal account existence
    token = new_opaque_token("empr")
    session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=utcnow() + timedelta(minutes=settings.password_reset_minutes),
            created_at=utcnow(),
        )
    )
    return token


async def consume_password_reset(session: AsyncSession, token: str, new_password: str) -> None:
    row = (
        await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_token(token))
        )
    ).scalar_one_or_none()
    if row is None or row.used_at is not None or row.expires_at < utcnow():
        raise AuthError("Invalid or expired reset link.")
    user = (await session.execute(select(User).where(User.id == row.user_id))).scalar_one()
    user.password_hash = hash_password(new_password)
    row.used_at = utcnow()
    await revoke_all_user_tokens(session, user.id)  # force re-login everywhere


# --- Context loading --------------------------------------------------------


async def load_memberships(session: AsyncSession, user: User) -> list[dict]:
    rows = (
        await session.execute(
            select(Organization, OrgMembership, User)
            .join(OrgMembership, OrgMembership.organization_id == Organization.id)
            .join(User, User.id == OrgMembership.user_id)
            .where(OrgMembership.user_id == user.id, OrgMembership.is_active.is_(True))
            .order_by(OrgMembership.is_default.desc(), Organization.name)
        )
    ).all()
    out = []
    for org, membership, _u in rows:
        perms = await role_permissions_for(session, membership.role_code)
        out.append(
            {
                "organization_id": org.id,
                "organization_name": org.name,
                "organization_slug": org.slug,
                "role_code": membership.role_code,
                "role_name": ROLES.get(membership.role_code, {}).get("name", membership.role_code),
                "is_default": membership.is_default,
                "is_demo": org.is_demo,
                "permissions": perms,
            }
        )
    return out


async def role_permissions_for(session: AsyncSession, role_code: str) -> list[str]:
    from app.auth.models import role_permissions as rp

    rows = (
        await session.execute(select(rp.c.permission_code).where(rp.c.role_code == role_code))
    ).all()
    return sorted(r[0] for r in rows)


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise NotFoundError("User not found.")
    return user


def all_permission_codes() -> list[str]:
    return sorted(PERMISSIONS.keys())
