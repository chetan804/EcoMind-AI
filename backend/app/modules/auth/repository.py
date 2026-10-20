"""Database access for refresh sessions and login-attempt counting. Never commits."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.auth.models import AuthSession

LOGIN_FAILED = "auth.login_failed"
LOGIN_SUCCEEDED = "auth.login"
REGISTERED = "auth.register"


def add_session(
    db: Session,
    *,
    user_id: uuid.UUID,
    family_id: uuid.UUID,
    token_hash: str,
    expires_at: datetime,
    user_agent: str | None,
    ip_address: str | None,
) -> AuthSession:
    session = AuthSession(
        user_id=user_id,
        family_id=family_id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    db.flush()
    return session


def get_session_for_update(db: Session, token_hash: str) -> AuthSession | None:
    """Lock the row so concurrent refreshes of one token serialise (exactly one wins)."""
    return db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_hash).with_for_update()
    )


def revoke_family(db: Session, family_id: uuid.UUID, now: datetime) -> int:
    result = db.execute(
        update(AuthSession)
        .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def revoke_all_for_user(db: Session, user_id: uuid.UUID, now: datetime) -> int:
    result = db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def failed_login_times(
    db: Session, *, email_sha256: str, since: datetime, limit: int
) -> list[datetime]:
    """Newest-first failure times for this email since ``since`` and since its last success."""
    last_success = (
        select(func.max(AuditLog.occurred_at))
        .where(
            AuditLog.action == LOGIN_SUCCEEDED,
            AuditLog.changes["email_sha256"].astext == email_sha256,
        )
        .scalar_subquery()
    )
    stmt = (
        select(AuditLog.occurred_at)
        .where(
            AuditLog.action == LOGIN_FAILED,
            AuditLog.changes["email_sha256"].astext == email_sha256,
            AuditLog.occurred_at >= since,
            AuditLog.occurred_at > func.coalesce(last_success, since),
        )
        .order_by(AuditLog.occurred_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def action_times_for_ip(
    db: Session, *, action: str, ip_address: str, since: datetime, limit: int
) -> list[datetime]:
    stmt = (
        select(AuditLog.occurred_at)
        .where(
            AuditLog.action == action,
            AuditLog.ip_address == ip_address,
            AuditLog.occurred_at >= since,
        )
        .order_by(AuditLog.occurred_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
