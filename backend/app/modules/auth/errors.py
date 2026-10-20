"""Auth-specific client errors. Each has a stable machine-readable ``code``."""

from __future__ import annotations

from app.core.exceptions import AppError, ConflictError, UnauthenticatedError


class InvalidCredentialsError(UnauthenticatedError):
    """Wrong email or password, unknown email, or deactivated account (indistinguishable)."""

    code = "invalid_credentials"


class InvalidRefreshTokenError(UnauthenticatedError):
    code = "invalid_refresh_token"
    keep_cookie = False  # an unusable cookie is cleared so the browser stops sending it


class RefreshTokenRaceError(InvalidRefreshTokenError):
    """The token was rotated moments ago by a concurrent request (for example another tab).

    The browser's cookie jar is shared, so the winning request has already stored the new cookie.
    Clearing the cookie here would sign the user out, so the router must leave it alone.
    """

    keep_cookie = True


class RefreshTokenReuseError(UnauthenticatedError):
    """A rotated token was replayed outside the grace window; the whole family was revoked."""

    code = "refresh_token_reused"


class EmailAlreadyRegisteredError(ConflictError):
    code = "email_already_registered"


class WeakPasswordError(AppError):
    status_code = 422
    code = "weak_password"


class MfaAlreadyEnabledError(ConflictError):
    code = "mfa_already_enabled"


class MfaNotEnabledError(ConflictError):
    code = "mfa_not_enabled"


class MfaEnrollmentNotStartedError(ConflictError):
    code = "mfa_enrollment_not_started"


class InvalidMfaCodeError(AppError):
    """A management action was refused because the code did not verify."""

    status_code = 422
    code = "invalid_mfa_code"


class MfaChallengeFailedError(UnauthenticatedError):
    """The sign-in second step failed: bad or expired challenge, or wrong code."""

    code = "invalid_mfa_code"


class MfaUnavailableError(AppError):
    """The stored secret cannot be decrypted (``SECRET_KEY`` changed): re-enrolment is needed."""

    status_code = 409
    code = "mfa_secret_unreadable"
