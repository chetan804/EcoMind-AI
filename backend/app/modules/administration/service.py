"""Administration: user accounts, roles, audit log and system information.

Business rules live here; row access stays in the ``users``, ``audit`` and ``auth`` repositories.
Every change is audited with before/after values and a mandatory reason.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.core.config import Settings
from app.core.exceptions import AppError, NotFoundError, UnprocessableError
from app.modules.administration.schemas import (
    AuditEntryOut,
    RoleOut,
    RolesRequest,
    SystemInfo,
    UserAdminOut,
)
from app.modules.audit import repository as audit_repository
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth import repository as auth_repository
from app.modules.auth.dependencies import Principal
from app.modules.classification import repository as classification
from app.modules.users import repository as users
from app.modules.users.models import User

ADMIN_ROLE = "administrator"


class SelfModificationError(AppError):
    status_code = 409
    code = "self_modification_forbidden"


class LastAdministratorError(AppError):
    status_code = 409
    code = "last_administrator"


def _out(db: Session, user: User) -> UserAdminOut:
    return _outs(db, [user])[0]


def _outs(db: Session, rows: list[User]) -> list[UserAdminOut]:
    ids = [u.id for u in rows]
    roles = users.roles_by_user(db, ids)
    with_mfa = auth_repository.users_with_mfa(db, ids)
    return [
        UserAdminOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            mfa_enabled=u.id in with_mfa,
            email_verified=u.email_verified_at is not None,
            roles=roles[u.id],
            created_at=u.created_at,
            last_login_at=u.last_login_at,
        )
        for u in rows
    ]


def _get(db: Session, user_id: uuid.UUID, *, lock: bool = False) -> User:
    if lock:
        db.execute(users.lock_statement(user_id))
    user = users.get_by_id(db, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def list_users(
    db: Session,
    params: PageParams,
    *,
    q: str | None,
    role: str | None,
    is_active: bool | None,
) -> Page[UserAdminOut]:
    rows, total = users.list_page(
        db,
        offset=params.offset,
        limit=params.limit,
        q_pattern=contains_pattern(q) if q else None,
        escape=LIKE_ESCAPE,
        role=role,
        is_active=is_active,
    )
    return Page.build(_outs(db, rows), total, params)


def get_user(db: Session, user_id: uuid.UUID) -> UserAdminOut:
    return _out(db, _get(db, user_id))


def list_roles(db: Session) -> list[RoleOut]:
    return [
        RoleOut(
            name=r.name,
            description=r.description,
            is_system=r.is_system,
            user_count=n,
            permissions=perms,
        )
        for r, perms, n in users.list_roles(db)
    ]


def _guard_not_self(principal: Principal, user_id: uuid.UUID) -> None:
    if principal.user_id == user_id:
        raise SelfModificationError(
            "Administrators cannot change their own roles or active state; ask another one"
        )


def _require_other_administrator(db: Session, user_id: uuid.UUID) -> None:
    """After changing ``user_id`` there must still be an active administrator."""
    remaining = [a for a in users.lock_active_administrators(db) if a != user_id]
    if not remaining:
        db.rollback()
        raise LastAdministratorError("The platform must keep at least one active administrator")


def set_roles(
    db: Session,
    principal: Principal,
    user_id: uuid.UUID,
    payload: RolesRequest,
    *,
    context: RequestContext,
) -> UserAdminOut:
    _guard_not_self(principal, user_id)
    names = sorted(set(payload.roles))
    found = users.roles_by_names(db, names)
    unknown = sorted(set(names) - {r.name for r in found})
    if unknown:
        raise UnprocessableError(f"Unknown role(s): {', '.join(unknown)}")
    user = _get(db, user_id, lock=True)
    before = users.role_names(db, user.id)
    if ADMIN_ROLE in before and ADMIN_ROLE not in names and user.is_active:
        _require_other_administrator(db, user.id)
    users.replace_roles(db, user.id, [r.id for r in found])
    audit.record(
        db,
        action="user.roles_changed",
        entity_type="user",
        entity_id=user.id,
        actor_id=principal.user_id,
        context=context,
        changes={"before": before, "after": names, "reason": payload.reason},
    )
    db.commit()
    return _out(db, user)


def set_active(
    db: Session,
    principal: Principal,
    user_id: uuid.UUID,
    *,
    active: bool,
    reason: str,
    context: RequestContext,
) -> UserAdminOut:
    _guard_not_self(principal, user_id)
    user = _get(db, user_id, lock=True)
    if user.is_active != active:
        if not active and ADMIN_ROLE in users.role_names(db, user.id):
            _require_other_administrator(db, user.id)
        user.is_active = active
        revoked = 0
        if not active:
            revoked = auth_repository.revoke_all_for_user(db, user.id, dt.datetime.now(dt.UTC))
        audit.record(
            db,
            action="user.activated" if active else "user.deactivated",
            entity_type="user",
            entity_id=user.id,
            actor_id=principal.user_id,
            context=context,
            changes={"is_active": active, "reason": reason, "sessions_revoked": revoked},
        )
        db.commit()
    return _out(db, user)


def reset_mfa(
    db: Session,
    principal: Principal,
    user_id: uuid.UUID,
    *,
    reason: str,
    context: RequestContext,
) -> UserAdminOut:
    """Remove a user's authenticator (lost phone and recovery codes). Signs them out everywhere."""
    _guard_not_self(principal, user_id)
    user = _get(db, user_id, lock=True)
    had_mfa = user_id in auth_repository.users_with_mfa(db, [user_id])
    if had_mfa:
        auth_repository.delete_factor(db, user.id)
        revoked = auth_repository.revoke_all_for_user(db, user.id, dt.datetime.now(dt.UTC))
        audit.record(
            db,
            action="user.mfa_reset",
            entity_type="user",
            entity_id=user.id,
            actor_id=principal.user_id,
            context=context,
            changes={"reason": reason, "sessions_revoked": revoked},
        )
        db.commit()
    return _out(db, user)


def list_audit(
    db: Session,
    params: PageParams,
    *,
    action: str | None,
    entity_type: str | None,
    entity_id: uuid.UUID | None,
    actor_id: uuid.UUID | None,
    occurred_from: dt.datetime | None,
    occurred_to: dt.datetime | None,
) -> Page[AuditEntryOut]:
    rows, total = audit_repository.list_page(
        db,
        offset=params.offset,
        limit=params.limit,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )
    items = [
        AuditEntryOut(
            id=e.id,
            occurred_at=e.occurred_at,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            actor_id=e.actor_id,
            actor_email=email,
            request_id=e.request_id,
            ip_address=e.ip_address,
            changes=e.changes,
        )
        for e, email in rows
    ]
    return Page.build(items, total, params)


def system_info(db: Session, settings: Settings) -> SystemInfo:
    revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    active = classification.active_version(db)
    return SystemInfo(
        environment=settings.environment,
        log_level=settings.log_level,
        access_token_expire_minutes=settings.access_token_expire_minutes,
        refresh_token_expire_days=settings.refresh_token_expire_days,
        refresh_cookie_secure=settings.refresh_cookie_secure,
        refresh_cookie_samesite=settings.refresh_cookie_samesite,
        cors_allowed_origins=list(settings.cors_allowed_origins),
        file_storage_backend=settings.file_storage_backend,
        max_upload_bytes=settings.max_upload_bytes,
        reward_points_per_kg=settings.reward_points_per_kg,
        database_revision=revision,
        active_model_version=active.version if active is not None else None,
    )
