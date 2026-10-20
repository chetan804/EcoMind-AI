"""TOTP multi-factor authentication: enrolment, sign-in second step, recovery codes.

Properties (covered by ``tests/api/test_mfa.py`` and ``tests/unit/test_totp.py``):
- The shared secret is encrypted at rest; it is shown once, during enrolment.
- Enrolment only takes effect once the user proves a valid code (no lock-out by a bad scan).
- A code is accepted once: the last accepted time step is stored (replay protection).
- Recovery codes (ten, 60 bits each) are stored as keyed hashes and work once.
- Second-step failures are limited to five per 15 minutes per user (429), derived from the
  audit log like password failures. Turning MFA off or re-issuing codes needs the password and a
  current code, so a stolen access token alone cannot weaken the account.
- The login challenge token is short-lived (5 minutes) and useless as an access token.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.common.time import utc_now
from app.core.config import Settings
from app.core.crypto import DecryptionError, decrypt_mfa_secret, encrypt_mfa_secret, keyed_hash
from app.core.exceptions import TooManyRequestsError, UnauthenticatedError
from app.core.security import (
    create_mfa_challenge_token,
    decode_mfa_challenge_token,
    verify_password,
)
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth import policy, repository, totp
from app.modules.auth.errors import (
    InvalidCredentialsError,
    InvalidMfaCodeError,
    MfaAlreadyEnabledError,
    MfaChallengeFailedError,
    MfaEnrollmentNotStartedError,
    MfaNotEnabledError,
    MfaUnavailableError,
)
from app.modules.auth.models import MfaFactor
from app.modules.auth.schemas import MfaEnrollOut, MfaStatusOut
from app.modules.users import repository as users
from app.modules.users.models import User

ISSUER = "EcoMind AI"
CHALLENGE_LIFETIME = timedelta(minutes=5)
RECOVERY_CODE_COUNT = 10
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
_RECOVERY_PURPOSE = "mfa-recovery"
_MAX_FAILURES = 5


def is_enabled(db: Session, user_id: uuid.UUID) -> bool:
    factor = repository.get_factor(db, user_id)
    return factor is not None and factor.confirmed_at is not None


def new_challenge(settings: Settings, user_id: uuid.UUID, *, now: datetime) -> tuple[str, int]:
    token = create_mfa_challenge_token(
        subject=user_id,
        secret_key=settings.secret_key.get_secret_value(),
        expires_in=CHALLENGE_LIFETIME,
        algorithm=settings.jwt_algorithm,
        now=now,
    )
    return token, int(CHALLENGE_LIFETIME.total_seconds())


def _normalise_recovery(code: str) -> str:
    return code.replace("-", "").replace(" ", "").upper()


def _recovery_hash(settings: Settings, user_id: uuid.UUID, code: str) -> str:
    return keyed_hash(
        settings.secret_key.get_secret_value(),
        _RECOVERY_PURPOSE,
        f"{user_id}:{_normalise_recovery(code)}",
    )


def _new_recovery_code() -> str:
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"


def _issue_recovery_codes(db: Session, settings: Settings, user_id: uuid.UUID) -> list[str]:
    codes = [_new_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
    repository.replace_recovery_codes(
        db, user_id, [_recovery_hash(settings, user_id, c) for c in codes]
    )
    return codes


def _secret(settings: Settings, factor: MfaFactor) -> str:
    try:
        return decrypt_mfa_secret(settings.secret_key.get_secret_value(), factor.secret_encrypted)
    except DecryptionError as exc:
        raise MfaUnavailableError(
            "The authenticator secret can no longer be read; an administrator must reset MFA"
        ) from exc


def _enforce_failure_limit(db: Session, user_id: uuid.UUID, now: datetime) -> None:
    times = repository.mfa_failed_times(
        db, user_id=user_id, since=now - policy.LOGIN_WINDOW, limit=_MAX_FAILURES
    )
    if len(times) >= _MAX_FAILURES:
        wait = max(1, int((times[-1] + policy.LOGIN_WINDOW - now).total_seconds()) + 1)
        raise TooManyRequestsError(
            "Too many incorrect verification codes. Try again later.",
            headers={"Retry-After": str(wait)},
        )


def _check_code(
    db: Session,
    settings: Settings,
    user: User,
    factor: MfaFactor,
    code: str,
    *,
    allow_recovery: bool,
    now: datetime,
) -> bool:
    """True when ``code`` is a fresh TOTP code or an unused recovery code. Records the use."""
    code = code.strip()
    if code.replace(" ", "").isdigit():
        step = totp.match_step(
            _secret(settings, factor),
            code.replace(" ", ""),
            now.timestamp(),
            last_used_step=factor.last_used_step,
        )
        if step is None:
            return False
        factor.last_used_step = step
        return True
    if allow_recovery:
        return repository.consume_recovery_code(
            db, user.id, _recovery_hash(settings, user.id, code), now
        )
    return False


def _fail(db: Session, user_id: uuid.UUID, context: RequestContext, reason: str) -> None:
    audit.record(
        db,
        action=repository.MFA_FAILED,
        entity_type="user",
        entity_id=user_id,
        actor_id=user_id,
        context=context,
        changes={"reason": reason},
    )
    db.commit()  # the failure must be counted although the request errors


def status(db: Session, user_id: uuid.UUID) -> MfaStatusOut:
    factor = repository.get_factor(db, user_id)
    confirmed = factor is not None and factor.confirmed_at is not None
    return MfaStatusOut(
        enabled=confirmed,
        pending_enrollment=factor is not None and not confirmed,
        enabled_at=factor.confirmed_at if factor is not None else None,
        recovery_codes_remaining=repository.unused_recovery_codes(db, user_id) if confirmed else 0,
    )


def begin_enrollment(
    db: Session, settings: Settings, user: User, *, context: RequestContext
) -> MfaEnrollOut:
    existing = repository.get_factor(db, user.id, for_update=True)
    if existing is not None and existing.confirmed_at is not None:
        raise MfaAlreadyEnabledError("Two-factor authentication is already turned on")
    secret = totp.generate_secret()
    repository.replace_pending_factor(
        db, user.id, encrypt_mfa_secret(settings.secret_key.get_secret_value(), secret)
    )
    audit.record(
        db,
        action="auth.mfa_enrolment_started",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
    )
    db.commit()
    return MfaEnrollOut(
        secret=secret,
        otpauth_uri=totp.provisioning_uri(secret, account=user.email, issuer=ISSUER),
        issuer=ISSUER,
        digits=totp.DIGITS,
        period_seconds=totp.PERIOD,
    )


def activate(
    db: Session, settings: Settings, user: User, code: str, *, context: RequestContext
) -> list[str]:
    now = utc_now()
    factor = repository.get_factor(db, user.id, for_update=True)
    if factor is None:
        raise MfaEnrollmentNotStartedError("Start enrolment first")
    if factor.confirmed_at is not None:
        raise MfaAlreadyEnabledError("Two-factor authentication is already turned on")
    _enforce_failure_limit(db, user.id, now)
    if not _check_code(db, settings, user, factor, code, allow_recovery=False, now=now):
        _fail(db, user.id, context, "activation")
        raise InvalidMfaCodeError("That code is not valid. Check the app and try again.")
    factor.confirmed_at = now
    codes = _issue_recovery_codes(db, settings, user.id)
    audit.record(
        db,
        action="auth.mfa_enabled",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
    )
    db.commit()
    return codes


def _require_proof(
    db: Session,
    settings: Settings,
    user: User,
    password: str,
    code: str,
    *,
    context: RequestContext,
) -> MfaFactor:
    now = utc_now()
    factor = repository.get_factor(db, user.id, for_update=True)
    if factor is None or factor.confirmed_at is None:
        raise MfaNotEnabledError("Two-factor authentication is not turned on")
    _enforce_failure_limit(db, user.id, now)
    if not verify_password(password, user.password_hash):
        _fail(db, user.id, context, "bad_password")
        raise InvalidCredentialsError("Password is incorrect")
    if not _check_code(db, settings, user, factor, code, allow_recovery=True, now=now):
        _fail(db, user.id, context, "bad_code")
        raise InvalidMfaCodeError("That code is not valid.")
    return factor


def disable(
    db: Session,
    settings: Settings,
    user: User,
    *,
    password: str,
    code: str,
    context: RequestContext,
) -> None:
    _require_proof(db, settings, user, password, code, context=context)
    repository.delete_factor(db, user.id)
    audit.record(
        db,
        action="auth.mfa_disabled",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
    )
    db.commit()


def regenerate_recovery_codes(
    db: Session,
    settings: Settings,
    user: User,
    *,
    password: str,
    code: str,
    context: RequestContext,
) -> list[str]:
    _require_proof(db, settings, user, password, code, context=context)
    codes = _issue_recovery_codes(db, settings, user.id)
    audit.record(
        db,
        action="auth.mfa_recovery_codes_regenerated",
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
    )
    db.commit()
    return codes


def complete_login(
    db: Session,
    settings: Settings,
    *,
    mfa_token: str,
    code: str,
    context: RequestContext,
) -> User:
    """Second sign-in step. Returns the user once the code verifies; the caller issues tokens."""
    now = utc_now()
    try:
        claims = decode_mfa_challenge_token(
            mfa_token,
            secret_key=settings.secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
        user_id = uuid.UUID(str(claims["sub"]))
    except (UnauthenticatedError, ValueError, KeyError) as exc:
        raise MfaChallengeFailedError("The sign-in session expired. Sign in again.") from exc
    user = users.get_by_id(db, user_id)
    factor = repository.get_factor(db, user_id, for_update=True) if user is not None else None
    if user is None or not user.is_active or factor is None or factor.confirmed_at is None:
        raise MfaChallengeFailedError("The sign-in session expired. Sign in again.")
    _enforce_failure_limit(db, user.id, now)
    if not _check_code(db, settings, user, factor, code, allow_recovery=True, now=now):
        _fail(db, user.id, context, "login")
        raise MfaChallengeFailedError("That code is not valid.")
    audit.record(
        db,
        action=repository.MFA_SUCCEEDED,
        entity_type="user",
        entity_id=user.id,
        actor_id=user.id,
        context=context,
    )
    return user
