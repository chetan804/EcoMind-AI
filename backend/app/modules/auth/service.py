"""Authentication use cases: register, login, refresh, logout, change password.

Transactions are owned here: each public function commits exactly once on success. Security
events that must outlive a rejected request (failed login, token-reuse revocation) are committed
before the error is raised.

Security properties (each covered by tests in ``tests/api/test_auth_*.py``):
- Argon2id password hashing; a dummy hash is verified for unknown emails so response time does not
  reveal which emails exist.
- One generic ``invalid_credentials`` error for unknown email, wrong password and deactivated user.
- Refresh tokens are opaque; only SHA-256 digests are stored. Every use rotates the token inside a
  ``family_id``. Replaying a rotated token after the grace window revokes the whole family.
- Brute-force limiting is derived from ``audit_logs`` (per email and per IP, 15 minute window).
- Password change and account deactivation revoke refresh sessions.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.core.config import Settings
from app.core.exceptions import TooManyRequestsError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    password_needs_rehash,
    verify_password,
)
from app.integrations.email.base import EmailMessage
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth import mfa, policy, recovery, repository
from app.modules.auth.errors import (
    EmailAlreadyRegisteredError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenRaceError,
    RefreshTokenReuseError,
    WeakPasswordError,
)
from app.modules.users import repository as users
from app.modules.users.models import User
from app.modules.users.rbac import DEFAULT_REGISTRATION_ROLE


@dataclass(frozen=True)
class UserView:
    id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
    permissions: list[str]
    email_verified: bool = False


@dataclass(frozen=True)
class AuthResult:
    user: UserView
    access_token: str
    refresh_token: str
    expires_in: int
    # Messages the router sends after the response (verification link, security notice).
    emails: tuple[EmailMessage, ...] = ()


@dataclass(frozen=True)
class MfaRequired:
    """Password accepted; the caller must complete the second step with this token."""

    mfa_token: str
    expires_in: int


@lru_cache
def _dummy_hash() -> str:
    return hash_password("not-a-real-account-password")


def _email_digest(email: str) -> str:
    """Stable pseudonym for audit rows so the log never stores attempted addresses in clear."""
    return hashlib.sha256(users.normalize_email(email).encode()).hexdigest()


def user_view(db: Session, user: User) -> UserView:
    return UserView(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=users.role_names(db, user.id),
        permissions=sorted(users.permission_codes(db, user.id)),
        email_verified=user.email_verified_at is not None,
    )


def _retry_after(times_newest_first: list[datetime], window: timedelta, now: datetime) -> int:
    """Seconds until the oldest counted event leaves the window (>= 1)."""
    oldest = times_newest_first[-1]
    return max(1, int((oldest + window - now).total_seconds()) + 1)


def _enforce_limit(
    times: list[datetime], *, maximum: int, window: timedelta, now: datetime, message: str
) -> None:
    if len(times) >= maximum:
        raise TooManyRequestsError(
            message, headers={"Retry-After": str(_retry_after(times, window, now))}
        )


def _issue_tokens(
    db: Session,
    settings: Settings,
    user: User,
    *,
    family_id: uuid.UUID,
    context: RequestContext,
    now: datetime,
) -> tuple[str, str, int]:
    refresh = generate_refresh_token()
    repository.add_session(
        db,
        user_id=user.id,
        family_id=family_id,
        token_hash=hash_refresh_token(refresh),
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        user_agent=context.user_agent,
        ip_address=context.ip_address,
    )
    lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    access = create_access_token(
        subject=user.id,
        secret_key=settings.secret_key.get_secret_value(),
        expires_in=lifetime,
        algorithm=settings.jwt_algorithm,
        now=now,
    )
    return access, refresh, int(lifetime.total_seconds())


def _validate_password(password: str, *, email: str, full_name: str) -> None:
    problems = policy.password_problems(password, email=email, full_name=full_name)
    if problems:
        raise WeakPasswordError(
            "Password does not meet the password policy",
            details=[
                {"location": ["body", "password"], "message": p, "type": "policy"} for p in problems
            ],
        )


def register(
    db: Session,
    settings: Settings,
    *,
    email: str,
    password: str,
    full_name: str,
    context: RequestContext,
) -> AuthResult:
    now = utc_now()
    if context.ip_address:
        recent = repository.action_times_for_ip(
            db,
            action=repository.REGISTERED,
            ip_address=context.ip_address,
            since=now - policy.REGISTER_WINDOW,
            limit=policy.MAX_REGISTRATIONS_PER_IP,
        )
        _enforce_limit(
            recent,
            maximum=policy.MAX_REGISTRATIONS_PER_IP,
            window=policy.REGISTER_WINDOW,
            now=now,
            message="Too many accounts created from this address. Try again later.",
        )
    _validate_password(password, email=email, full_name=full_name)
    if users.get_by_email(db, email) is not None:
        raise EmailAlreadyRegisteredError("An account with this email already exists")

    role = users.get_role_by_name(db, DEFAULT_REGISTRATION_ROLE)
    if role is None:  # the 0002 seed migration was not applied: fail loudly, never grant silently
        raise RuntimeError(
            f"Role {DEFAULT_REGISTRATION_ROLE!r} is missing; run database migrations"
        )
    try:
        user = users.add(
            db, email=email, password_hash=hash_password(password), full_name=full_name
        )
    except IntegrityError as exc:  # lost a race with a concurrent registration of the same email
        db.rollback()
        raise EmailAlreadyRegisteredError("An account with this email already exists") from exc
    users.assign_role(db, user_id=user.id, role_id=role.id)
    audit.record(
        db,
        action=repository.REGISTERED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
        changes={"role": DEFAULT_REGISTRATION_ROLE},
    )
    verification = recovery.verification_for_new_account(
        db, settings, user, context=context, now=now
    )
    access, refresh, expires_in = _issue_tokens(
        db, settings, user, family_id=uuid.uuid4(), context=context, now=now
    )
    view = user_view(db, user)
    db.commit()
    return AuthResult(
        view, access, refresh, expires_in, emails=(verification,) if verification else ()
    )


def login(
    db: Session,
    settings: Settings,
    *,
    email: str,
    password: str,
    context: RequestContext,
) -> AuthResult | MfaRequired:
    now = utc_now()
    digest = _email_digest(email)
    window_start = now - policy.LOGIN_WINDOW

    _enforce_limit(
        repository.failed_login_times(
            db,
            email_sha256=digest,
            since=window_start,
            limit=policy.MAX_FAILED_LOGINS_PER_EMAIL,
        ),
        maximum=policy.MAX_FAILED_LOGINS_PER_EMAIL,
        window=policy.LOGIN_WINDOW,
        now=now,
        message="Too many failed sign-in attempts. Try again later.",
    )
    if context.ip_address:
        _enforce_limit(
            repository.action_times_for_ip(
                db,
                action=repository.LOGIN_FAILED,
                ip_address=context.ip_address,
                since=window_start,
                limit=policy.MAX_FAILED_LOGINS_PER_IP,
            ),
            maximum=policy.MAX_FAILED_LOGINS_PER_IP,
            window=policy.LOGIN_WINDOW,
            now=now,
            message="Too many failed sign-in attempts from this address. Try again later.",
        )

    user = users.get_by_email(db, email)
    # Always verify against *some* hash so timing does not reveal whether the email exists.
    password_ok = verify_password(password, user.password_hash if user else _dummy_hash())
    if user is None or not password_ok or not user.is_active:
        audit.record(
            db,
            action=repository.LOGIN_FAILED,
            entity_type="user_login",
            entity_id=user.id if user else None,
            context=context,
            changes={"email_sha256": digest},
        )
        db.commit()  # the failure must be counted even though this request errors
        raise InvalidCredentialsError("Invalid email or password")

    if settings.email_verification_required and user.email_verified_at is None:
        # Only after the password was proven, so this reveals nothing to someone without it.
        raise EmailNotVerifiedError(
            "Confirm your e-mail address to sign in. Request a new confirmation link from the "
            "sign-in page."
        )
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    if mfa.is_enabled(db, user.id):
        # Password accepted, but no session yet: the second step proves the authenticator code.
        token, expires_in = mfa.new_challenge(settings, user.id, now=now)
        db.commit()
        return MfaRequired(token, expires_in)
    return finish_login(db, settings, user, context=context)


def finish_login(
    db: Session, settings: Settings, user: User, *, context: RequestContext
) -> AuthResult:
    """Issue the session for a user who has passed every required sign-in step."""
    now = utc_now()
    user.last_login_at = now
    access, refresh, expires_in = _issue_tokens(
        db, settings, user, family_id=uuid.uuid4(), context=context, now=now
    )
    audit.record(
        db,
        action=repository.LOGIN_SUCCEEDED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
        changes={"email_sha256": _email_digest(user.email)},
    )
    view = user_view(db, user)
    db.commit()
    return AuthResult(view, access, refresh, expires_in)


def refresh(
    db: Session,
    settings: Settings,
    *,
    refresh_token: str | None,
    context: RequestContext,
) -> AuthResult:
    if not refresh_token:
        raise InvalidRefreshTokenError("Refresh token is missing")
    now = utc_now()
    session = repository.get_session_for_update(db, hash_refresh_token(refresh_token))
    if session is None or session.revoked_at is not None:
        raise InvalidRefreshTokenError("Refresh token is invalid or expired")

    if session.rotated_at is not None:
        age = (now - session.rotated_at).total_seconds()
        if age <= policy.REFRESH_REUSE_GRACE_SECONDS:
            raise RefreshTokenRaceError("Refresh token was just used; retry with the new one")
        repository.revoke_family(db, session.family_id, now)
        audit.record(
            db,
            action="auth.refresh_reuse_detected",
            entity_type="user",
            entity_id=session.user_id,
            actor_id=session.user_id,
            context=context,
            changes={"family_id": str(session.family_id)},
        )
        db.commit()
        raise RefreshTokenReuseError("Session ended because a refresh token was reused")

    if session.expires_at <= now:
        raise InvalidRefreshTokenError("Refresh token is invalid or expired")
    user = users.get_by_id(db, session.user_id)
    if user is None or not user.is_active:
        repository.revoke_family(db, session.family_id, now)
        db.commit()
        raise InvalidRefreshTokenError("Refresh token is invalid or expired")

    session.rotated_at = now
    access, new_refresh, expires_in = _issue_tokens(
        db, settings, user, family_id=session.family_id, context=context, now=now
    )
    view = user_view(db, user)
    db.commit()
    return AuthResult(view, access, new_refresh, expires_in)


def logout(db: Session, *, refresh_token: str | None, context: RequestContext) -> None:
    """Revoke the session family of the presented token. Idempotent; never reveals validity."""
    if not refresh_token:
        return
    session = repository.get_session_for_update(db, hash_refresh_token(refresh_token))
    if session is None:
        return
    count = repository.revoke_family(db, session.family_id, utc_now())
    audit.record(
        db,
        action="auth.logout",
        entity_type="user",
        entity_id=session.user_id,
        actor_id=session.user_id,
        context=context,
        changes={"sessions_revoked": count},
    )
    db.commit()


def change_password(
    db: Session,
    settings: Settings,
    *,
    user_id: uuid.UUID,
    current_password: str,
    new_password: str,
    context: RequestContext,
) -> AuthResult:
    now = utc_now()
    user = users.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise InvalidCredentialsError("Invalid password")
    if not verify_password(current_password, user.password_hash):
        audit.record(
            db,
            action="auth.password_change_failed",
            entity_type="user",
            entity_id=user.id,
            actor_id=user.id,
            context=context,
        )
        db.commit()
        raise InvalidCredentialsError("Current password is incorrect")
    _validate_password(new_password, email=user.email, full_name=user.full_name)
    if verify_password(new_password, user.password_hash):
        raise WeakPasswordError(
            "Choose a password different from the current one",
            details=[
                {
                    "location": ["body", "new_password"],
                    "message": "The new password must differ from the current one.",
                    "type": "policy",
                }
            ],
        )
    user.password_hash = hash_password(new_password)
    revoked = repository.revoke_all_for_user(db, user.id, now)
    access, refresh_token, expires_in = _issue_tokens(
        db, settings, user, family_id=uuid.uuid4(), context=context, now=now
    )
    audit.record(
        db,
        action="auth.password_changed",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
        changes={"sessions_revoked": revoked},
    )
    view = user_view(db, user)
    db.commit()
    notice = recovery.password_changed_notice(user, how="from the account page")
    return AuthResult(
        view, access, refresh_token, expires_in, emails=(notice,) if settings.email_enabled else ()
    )
