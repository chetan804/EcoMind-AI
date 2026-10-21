"""Database access for refresh sessions and login-attempt counting. Never commits."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog
from app.modules.auth.models import (
    AccountToken,
    AccountTokenPurpose,
    AuthSession,
    MfaFactor,
    MfaRecoveryCode,
)

LOGIN_FAILED = "auth.login_failed"
LOGIN_SUCCEEDED = "auth.login"
REGISTERED = "auth.register"
PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"  # noqa: S105 - audit action name, not a credential
PASSWORD_RESET_COMPLETED = "auth.password_reset_completed"  # noqa: S105 - audit action name, not a credential
EMAIL_VERIFICATION_REQUESTED = "auth.email_verification_requested"
# Sent automatically at registration: audited, but not counted against the request limits.
EMAIL_VERIFICATION_ON_REGISTER = "auth.email_verification_on_register"
EMAIL_VERIFIED = "auth.email_verified"
ACCOUNT_TOKEN_REJECTED = "auth.account_token_rejected"  # noqa: S105 - audit action name, not a credential


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
            # A completed password reset proves control of the mailbox: it clears the lockout too.
            AuditLog.action.in_((LOGIN_SUCCEEDED, PASSWORD_RESET_COMPLETED)),
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


MFA_FAILED = "auth.mfa_failed"
MFA_SUCCEEDED = "auth.mfa_succeeded"


def get_factor(db: Session, user_id: uuid.UUID, *, for_update: bool = False) -> MfaFactor | None:
    stmt = select(MfaFactor).where(MfaFactor.user_id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def replace_pending_factor(db: Session, user_id: uuid.UUID, secret_encrypted: str) -> MfaFactor:
    """Start (or restart) enrolment. A confirmed factor is never replaced by this function."""
    factor = get_factor(db, user_id, for_update=True)
    if factor is None:
        factor = MfaFactor(user_id=user_id, secret_encrypted=secret_encrypted)
        db.add(factor)
    else:
        factor.secret_encrypted = secret_encrypted
        factor.last_used_step = None
    db.flush()
    return factor


def delete_factor(db: Session, user_id: uuid.UUID) -> None:
    db.execute(delete(MfaFactor).where(MfaFactor.user_id == user_id))
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id))


def replace_recovery_codes(db: Session, user_id: uuid.UUID, code_hashes: list[str]) -> None:
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user_id))
    for code_hash in code_hashes:
        db.add(MfaRecoveryCode(user_id=user_id, code_hash=code_hash))
    db.flush()


def consume_recovery_code(db: Session, user_id: uuid.UUID, code_hash: str, now: datetime) -> bool:
    """Mark the code used. The single UPDATE makes concurrent use of one code succeed once."""
    result = db.execute(
        update(MfaRecoveryCode)
        .where(
            MfaRecoveryCode.user_id == user_id,
            MfaRecoveryCode.code_hash == code_hash,
            MfaRecoveryCode.used_at.is_(None),
        )
        .values(used_at=now)
    )
    return bool(result.rowcount)  # type: ignore[attr-defined]


def unused_recovery_codes(db: Session, user_id: uuid.UUID) -> int:
    stmt = (
        select(func.count())
        .select_from(MfaRecoveryCode)
        .where(MfaRecoveryCode.user_id == user_id, MfaRecoveryCode.used_at.is_(None))
    )
    return int(db.execute(stmt).scalar_one())


def mfa_failed_times(
    db: Session, *, user_id: uuid.UUID, since: datetime, limit: int
) -> list[datetime]:
    """Newest-first second-step failures since ``since`` and since the last success."""
    last_success = (
        select(func.max(AuditLog.occurred_at))
        .where(AuditLog.action == MFA_SUCCEEDED, AuditLog.entity_id == user_id)
        .scalar_subquery()
    )
    stmt = (
        select(AuditLog.occurred_at)
        .where(
            AuditLog.action == MFA_FAILED,
            AuditLog.entity_id == user_id,
            AuditLog.occurred_at >= since,
            AuditLog.occurred_at > func.coalesce(last_success, since),
        )
        .order_by(AuditLog.occurred_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def users_with_mfa(db: Session, user_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """Those of ``user_ids`` that have a confirmed authenticator."""
    if not user_ids:
        return set()
    stmt = select(MfaFactor.user_id).where(
        MfaFactor.user_id.in_(user_ids), MfaFactor.confirmed_at.is_not(None)
    )
    return set(db.scalars(stmt))


def action_times_for_email(
    db: Session, *, action: str, email_sha256: str, since: datetime, limit: int
) -> list[datetime]:
    """Newest-first times of ``action`` rows recorded for this address digest since ``since``."""
    stmt = (
        select(AuditLog.occurred_at)
        .where(
            AuditLog.action == action,
            AuditLog.changes["email_sha256"].astext == email_sha256,
            AuditLog.occurred_at >= since,
        )
        .order_by(AuditLog.occurred_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def add_account_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    purpose: AccountTokenPurpose,
    token_hash: str,
    email: str,
    expires_at: datetime,
    requested_ip: str | None,
) -> AccountToken:
    token = AccountToken(
        user_id=user_id,
        purpose=purpose,
        token_hash=token_hash,
        email=email,
        expires_at=expires_at,
        requested_ip=requested_ip,
    )
    db.add(token)
    db.flush()
    return token


def get_account_token_for_update(
    db: Session, token_hash: str, purpose: AccountTokenPurpose
) -> AccountToken | None:
    """Lock the row so concurrent uses of one link serialise (exactly one wins)."""
    return db.scalar(
        select(AccountToken)
        .where(AccountToken.token_hash == token_hash, AccountToken.purpose == purpose)
        .with_for_update()
    )


def consume_outstanding_tokens(
    db: Session, user_id: uuid.UUID, purpose: AccountTokenPurpose, now: datetime
) -> int:
    """Mark every unused token of this purpose consumed (a newer link replaces older ones)."""
    result = db.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == purpose,
            AccountToken.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def purge_account_tokens(db: Session, *, older_than: datetime) -> int:
    """Delete tokens that expired, or were consumed, before ``older_than`` (housekeeping)."""
    result = db.execute(
        delete(AccountToken).where(
            (AccountToken.expires_at < older_than)
            | (AccountToken.consumed_at.is_not(None) & (AccountToken.consumed_at < older_than))
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
