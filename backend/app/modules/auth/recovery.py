"""Account recovery: password reset and e-mail verification by one-time e-mailed links.

Security properties (each covered by ``tests/api/test_account_recovery.py``):
- Tokens are 256-bit random values; only their SHA-256 digest is stored. A link works once, expires
  (30 minutes for a reset, 24 hours for verification by default) and a newer link replaces older
  ones. The token travels in the URL *fragment* (``#token=``) so it never reaches server logs or
  ``Referer`` headers; the web app removes it from the address bar after reading it.
- ``request`` endpoints answer the same ``202`` for known, unknown and deactivated addresses and
  for per-address throttling, so they cannot be used to find out who has an account.
- Rate limits derive from ``audit_logs`` (like the sign-in limits), so they hold across workers:
  3 messages per address per hour, 10 requests per IP per hour (429), 20 rejected links per IP per
  15 minutes (429).
- Completing a reset revokes every refresh session, clears the sign-in lockout and sends a notice.
  It does **not** remove two-factor authentication: the next sign-in still asks for the code.
- Nothing here sends mail itself: functions return :class:`EmailMessage` objects that the router
  schedules after the response, so SMTP latency cannot leak whether an address exists.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta
from typing import NoReturn

from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.core.config import Settings
from app.core.exceptions import TooManyRequestsError
from app.core.security import (
    generate_one_time_token,
    hash_one_time_token,
    hash_password,
)
from app.integrations.email.base import EmailMessage
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth import policy, repository
from app.modules.auth.errors import (
    EmailNotConfiguredError,
    InvalidAccountTokenError,
    WeakPasswordError,
)
from app.modules.auth.models import AccountToken as AccountTokenRow
from app.modules.auth.models import AccountTokenPurpose
from app.modules.users import repository as users
from app.modules.users.models import User

RESET_PATH = "/reset-password"
VERIFY_PATH = "/verify-email"


def _digest(email: str) -> str:
    return hashlib.sha256(users.normalize_email(email).encode()).hexdigest()


def _retry_after(times_newest_first: list[datetime], window: timedelta, now: datetime) -> int:
    oldest = times_newest_first[-1]
    return max(1, int((oldest + window - now).total_seconds()) + 1)


def _require_email(settings: Settings) -> None:
    if not settings.email_enabled:
        raise EmailNotConfiguredError(
            "E-mail delivery is not configured on this server. Ask an administrator for help."
        )


def _enforce_ip_limit(
    db: Session,
    *,
    action: str,
    context: RequestContext,
    maximum: int,
    window: timedelta,
    now: datetime,
) -> None:
    if not context.ip_address:
        return
    times = repository.action_times_for_ip(
        db, action=action, ip_address=context.ip_address, since=now - window, limit=maximum
    )
    if len(times) >= maximum:
        raise TooManyRequestsError(
            "Too many requests from this address. Try again later.",
            headers={"Retry-After": str(_retry_after(times, window, now))},
        )


def _link(settings: Settings, path: str, token: str) -> str:
    return f"{settings.app_base_url}{path}#token={token}"


def _issue(
    db: Session,
    settings: Settings,
    user: User,
    purpose: AccountTokenPurpose,
    *,
    lifetime: timedelta,
    now: datetime,
    context: RequestContext,
) -> str:
    """Replace any outstanding link of this purpose with a new one; return the raw token."""
    repository.consume_outstanding_tokens(db, user.id, purpose, now)
    token = generate_one_time_token()
    repository.add_account_token(
        db,
        user_id=user.id,
        purpose=purpose,
        token_hash=hash_one_time_token(token),
        email=user.email,
        expires_at=now + lifetime,
        requested_ip=context.ip_address,
    )
    return token


# --- message builders -------------------------------------------------------------------------


def _reset_message(settings: Settings, user: User, token: str) -> EmailMessage:
    minutes = settings.password_reset_token_minutes
    return EmailMessage(
        to=user.email,
        subject="Reset your EcoMind AI password",
        purpose="password_reset",
        body=(
            f"Hello {user.full_name},\n\n"
            "Someone asked to reset the password of your EcoMind AI account. Open this link to "
            "choose a new one:\n\n"
            f"{_link(settings, RESET_PATH, token)}\n\n"
            f"The link works once and expires in {minutes} minutes. If you did not ask for this, "
            "ignore this message: your password has not changed.\n"
        ),
    )


def _verification_message(settings: Settings, user: User, token: str) -> EmailMessage:
    hours = settings.email_verification_token_hours
    return EmailMessage(
        to=user.email,
        subject="Confirm your EcoMind AI e-mail address",
        purpose="email_verification",
        body=(
            f"Hello {user.full_name},\n\n"
            "Confirm that this is your e-mail address by opening this link:\n\n"
            f"{_link(settings, VERIFY_PATH, token)}\n\n"
            f"The link works once and expires in {hours} hours. If you did not create an EcoMind "
            "AI account, ignore this message.\n"
        ),
    )


def password_changed_notice(user: User, *, how: str) -> EmailMessage:
    """Security notice after a password change or reset (no link, so nothing to steal)."""
    return EmailMessage(
        to=user.email,
        subject="Your EcoMind AI password was changed",
        purpose="password_changed_notice",
        body=(
            f"Hello {user.full_name},\n\n"
            f"The password of your EcoMind AI account was changed ({how}). All other devices "
            "were signed out.\n\n"
            "If this was not you, reset your password now from the sign-in page and contact an "
            "administrator.\n"
        ),
    )


# --- use cases --------------------------------------------------------------------------------


def verification_for_new_account(
    db: Session, settings: Settings, user: User, *, context: RequestContext, now: datetime
) -> EmailMessage | None:
    """Called by registration: the first verification link, or ``None`` without e-mail delivery."""
    if not settings.email_enabled or user.email_verified_at is not None:
        return None
    token = _issue(
        db,
        settings,
        user,
        AccountTokenPurpose.EMAIL_VERIFICATION,
        lifetime=timedelta(hours=settings.email_verification_token_hours),
        now=now,
        context=context,
    )
    audit.record(
        db,
        action=repository.EMAIL_VERIFICATION_ON_REGISTER,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
        changes={"email_sha256": _digest(user.email)},
    )
    return _verification_message(settings, user, token)


def request_password_reset(
    db: Session, settings: Settings, *, email: str, context: RequestContext
) -> EmailMessage | None:
    """Record the request and return the message to send (``None`` = send nothing)."""
    _require_email(settings)
    now = utc_now()
    _enforce_ip_limit(
        db,
        action=repository.PASSWORD_RESET_REQUESTED,
        context=context,
        maximum=policy.MAX_ACCOUNT_EMAIL_REQUESTS_PER_IP,
        window=policy.ACCOUNT_EMAIL_WINDOW,
        now=now,
    )
    digest = _digest(email)
    recent = repository.action_times_for_email(
        db,
        action=repository.PASSWORD_RESET_REQUESTED,
        email_sha256=digest,
        since=now - policy.ACCOUNT_EMAIL_WINDOW,
        limit=policy.MAX_ACCOUNT_EMAILS_PER_ADDRESS,
    )
    throttled = len(recent) >= policy.MAX_ACCOUNT_EMAILS_PER_ADDRESS
    user = users.get_by_email(db, email)
    eligible = user is not None and user.is_active and not throttled
    message: EmailMessage | None = None
    if eligible and user is not None:
        token = _issue(
            db,
            settings,
            user,
            AccountTokenPurpose.PASSWORD_RESET,
            lifetime=timedelta(minutes=settings.password_reset_token_minutes),
            now=now,
            context=context,
        )
        message = _reset_message(settings, user, token)
    audit.record(
        db,
        action=repository.PASSWORD_RESET_REQUESTED,
        entity_type="user",
        entity_id=user.id if user else None,
        context=context,
        changes={"email_sha256": digest, "message_queued": message is not None},
    )
    db.commit()
    return message


def confirm_password_reset(
    db: Session,
    settings: Settings,
    *,
    token: str,
    new_password: str,
    context: RequestContext,
) -> EmailMessage:
    now = utc_now()
    _enforce_ip_limit(
        db,
        action=repository.ACCOUNT_TOKEN_REJECTED,
        context=context,
        maximum=policy.MAX_TOKEN_REJECTIONS_PER_IP,
        window=policy.TOKEN_REJECT_WINDOW,
        now=now,
    )
    row, user = _usable_token(db, token, AccountTokenPurpose.PASSWORD_RESET, now, context)
    problems = policy.password_problems(new_password, email=user.email, full_name=user.full_name)
    if problems:  # the link stays valid so the user can try again
        raise WeakPasswordError(
            "Password does not meet the password policy",
            details=[
                {"location": ["body", "new_password"], "message": p, "type": "policy"}
                for p in problems
            ],
        )
    user.password_hash = hash_password(new_password)
    repository.consume_outstanding_tokens(db, user.id, AccountTokenPurpose.PASSWORD_RESET, now)
    revoked = repository.revoke_all_for_user(db, user.id, now)
    if user.email_verified_at is None and row.email == user.email:
        user.email_verified_at = now  # the link reached the mailbox, which proves control of it
    audit.record(
        db,
        action=repository.PASSWORD_RESET_COMPLETED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
        changes={"sessions_revoked": revoked, "email_sha256": _digest(user.email)},
    )
    db.commit()
    return password_changed_notice(user, how="using a reset link")


def request_email_verification(
    db: Session, settings: Settings, *, email: str, context: RequestContext
) -> EmailMessage | None:
    """Send a (new) verification link. Public so that a user who cannot sign in yet can ask."""
    _require_email(settings)
    now = utc_now()
    _enforce_ip_limit(
        db,
        action=repository.EMAIL_VERIFICATION_REQUESTED,
        context=context,
        maximum=policy.MAX_ACCOUNT_EMAIL_REQUESTS_PER_IP,
        window=policy.ACCOUNT_EMAIL_WINDOW,
        now=now,
    )
    digest = _digest(email)
    recent = repository.action_times_for_email(
        db,
        action=repository.EMAIL_VERIFICATION_REQUESTED,
        email_sha256=digest,
        since=now - policy.ACCOUNT_EMAIL_WINDOW,
        limit=policy.MAX_ACCOUNT_EMAILS_PER_ADDRESS,
    )
    throttled = len(recent) >= policy.MAX_ACCOUNT_EMAILS_PER_ADDRESS
    user = users.get_by_email(db, email)
    message: EmailMessage | None = None
    if user is not None and user.is_active and user.email_verified_at is None and not throttled:
        token = _issue(
            db,
            settings,
            user,
            AccountTokenPurpose.EMAIL_VERIFICATION,
            lifetime=timedelta(hours=settings.email_verification_token_hours),
            now=now,
            context=context,
        )
        message = _verification_message(settings, user, token)
    audit.record(
        db,
        action=repository.EMAIL_VERIFICATION_REQUESTED,
        entity_type="user",
        entity_id=user.id if user else None,
        context=context,
        changes={"email_sha256": digest, "message_queued": message is not None},
    )
    db.commit()
    return message


def confirm_email_verification(
    db: Session, settings: Settings, *, token: str, context: RequestContext
) -> None:
    now = utc_now()
    _enforce_ip_limit(
        db,
        action=repository.ACCOUNT_TOKEN_REJECTED,
        context=context,
        maximum=policy.MAX_TOKEN_REJECTIONS_PER_IP,
        window=policy.TOKEN_REJECT_WINDOW,
        now=now,
    )
    row, user = _usable_token(db, token, AccountTokenPurpose.EMAIL_VERIFICATION, now, context)
    if row.email != user.email:  # the account's address changed after the link was sent
        _reject(db, context, reason="address_changed", user_id=user.id)
    repository.consume_outstanding_tokens(db, user.id, AccountTokenPurpose.EMAIL_VERIFICATION, now)
    if user.email_verified_at is None:
        user.email_verified_at = now
    audit.record(
        db,
        action=repository.EMAIL_VERIFIED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
        changes={"email_sha256": _digest(user.email)},
    )
    db.commit()


def purge_expired_tokens(db: Session, *, keep_days: int = 7) -> int:
    """Housekeeping: delete tokens that expired or were used more than ``keep_days`` ago."""
    count = repository.purge_account_tokens(db, older_than=utc_now() - timedelta(days=keep_days))
    db.commit()
    return count


# --- helpers ----------------------------------------------------------------------------------


def _reject(
    db: Session, context: RequestContext, *, reason: str, user_id: uuid.UUID | None = None
) -> NoReturn:
    """Count the failure (it must outlive this request) and raise the one generic error."""
    audit.record(
        db,
        action=repository.ACCOUNT_TOKEN_REJECTED,
        entity_type="user",
        entity_id=user_id,
        context=context,
        changes={"reason": reason},
    )
    db.commit()
    raise InvalidAccountTokenError("This link is invalid or has expired. Request a new one.")


def _usable_token(
    db: Session,
    token: str,
    purpose: AccountTokenPurpose,
    now: datetime,
    context: RequestContext,
) -> tuple[AccountTokenRow, User]:
    row = repository.get_account_token_for_update(db, hash_one_time_token(token), purpose)
    if row is None:
        _reject(db, context, reason="unknown")
    if row.consumed_at is not None:
        _reject(db, context, reason="already_used", user_id=row.user_id)
    if row.expires_at <= now:
        _reject(db, context, reason="expired", user_id=row.user_id)
    user = users.get_by_id(db, row.user_id)
    if user is None or not user.is_active:
        _reject(db, context, reason="account_unavailable", user_id=row.user_id)
    return row, user
