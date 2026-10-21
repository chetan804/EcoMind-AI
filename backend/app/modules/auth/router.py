"""Auth endpoints, mounted at ``/api/v1/auth``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Request, Response, status

from app.api.deps import AppSettings, DbSession
from app.core.config import Settings
from app.core.exceptions import AppError, UnauthenticatedError, error_response
from app.integrations.email.base import EmailMessage, EmailSender
from app.integrations.email.factory import deliver
from app.modules.audit.service import RequestContext
from app.modules.auth import mfa, recovery, service
from app.modules.auth.dependencies import (
    CurrentPrincipal,
    require_csrf_header,
)
from app.modules.auth.schemas import (
    AcceptedOut,
    AuthConfigOut,
    AuthResponse,
    ChangePasswordRequest,
    EmailVerificationConfirmRequest,
    EmailVerificationRequest,
    LoginRequest,
    MfaChallenge,
    MfaCodeRequest,
    MfaEnrollOut,
    MfaProofRequest,
    MfaRecoveryCodesOut,
    MfaStatusOut,
    MfaVerifyRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    UserOut,
)
from app.modules.users import repository as users
from app.modules.users.models import User

router = APIRouter()

REFRESH_COOKIE = "ecomind_refresh"
# The cookie is only ever sent to the auth endpoints, never with ordinary API calls.
REFRESH_COOKIE_PATH = "/api/v1/auth"


def get_email_sender(request: Request) -> EmailSender:
    sender: EmailSender = request.app.state.email_sender
    return sender


Mailer = Annotated[EmailSender, Depends(get_email_sender)]


def _send_after_response(
    background: BackgroundTasks, sender: EmailSender, messages: tuple[EmailMessage, ...]
) -> None:
    """Deliver after the response so mail-server latency cannot reveal anything to the caller."""
    for message in messages:
        background.add_task(deliver, sender, message)


def _set_refresh_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.refresh_cookie_secure,
        samesite=settings.refresh_cookie_samesite,
    )


def _body(result: service.AuthResult) -> AuthResponse:
    user = result.user
    return AuthResponse(
        access_token=result.access_token,
        expires_in=result.expires_in,
        user=UserOut(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            roles=user.roles,
            permissions=user.permissions,
            email_verified=user.email_verified,
            mfa_enrollment_required=user.mfa_enrollment_required,
        ),
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    mailer: Mailer,
) -> AuthResponse:
    """Create a ``citizen`` account and sign it in. Other roles are assigned by administrators."""
    result = service.register(
        db,
        settings,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
        context=RequestContext.from_request(request),
    )
    _send_after_response(background, mailer, result.emails)
    _set_refresh_cookie(response, settings, result.refresh_token)
    _no_store(response)
    return _body(result)


@router.post("/login", response_model=AuthResponse | MfaChallenge)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> AuthResponse | MfaChallenge:
    """Sign in. Accounts with two-factor authentication get an ``MfaChallenge`` (no session
    yet); complete it with ``POST /auth/mfa/verify``."""
    result = service.login(
        db,
        settings,
        email=payload.email,
        password=payload.password,
        context=RequestContext.from_request(request),
    )
    _no_store(response)
    if isinstance(result, service.MfaRequired):
        return MfaChallenge(mfa_token=result.mfa_token, expires_in=result.expires_in)
    _set_refresh_cookie(response, settings, result.refresh_token)
    return _body(result)


@router.post("/mfa/verify", response_model=AuthResponse)
def mfa_verify(
    payload: MfaVerifyRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> AuthResponse:
    """Second sign-in step: a 6-digit authenticator code or a recovery code."""
    context = RequestContext.from_request(request)
    user = mfa.complete_login(
        db, settings, mfa_token=payload.mfa_token, code=payload.code, context=context
    )
    result = service.finish_login(db, settings, user, context=context)
    _set_refresh_cookie(response, settings, result.refresh_token)
    _no_store(response)
    return _body(result)


@router.post(
    "/refresh",
    response_model=AuthResponse,
    dependencies=[Depends(require_csrf_header)],
)
def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> AuthResponse | Response:
    """Rotate the refresh cookie and return a new access token."""
    try:
        result = service.refresh(
            db,
            settings,
            refresh_token=refresh_token,
            context=RequestContext.from_request(request),
        )
    except AppError as exc:
        # Headers set on the injected ``response`` are discarded when an exception propagates,
        # so build the error response here to be able to clear the unusable cookie.
        error = error_response(
            request, exc.status_code, exc.code, exc.message, exc.details, headers=exc.headers
        )
        if not getattr(exc, "keep_cookie", False):
            _clear_refresh_cookie(error, settings)
        return error
    _set_refresh_cookie(response, settings, result.refresh_token)
    _no_store(response)
    return _body(result)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf_header)],
)
def logout(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    service.logout(db, refresh_token=refresh_token, context=RequestContext.from_request(request))
    out = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(out, settings)
    return out


@router.get("/me", response_model=UserOut)
def me(principal: CurrentPrincipal) -> UserOut:
    return UserOut(
        id=principal.user_id,
        email=principal.email,
        full_name=principal.full_name,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
        email_verified=principal.email_verified,
        mfa_enrollment_required=principal.mfa_enrollment_required,
    )


@router.post("/change-password", response_model=AuthResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    principal: CurrentPrincipal,
    db: DbSession,
    settings: AppSettings,
    mailer: Mailer,
) -> AuthResponse:
    """Change the password, revoke every other session and start a fresh one for this device."""
    result = service.change_password(
        db,
        settings,
        user_id=principal.user_id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        context=RequestContext.from_request(request),
    )
    _send_after_response(background, mailer, result.emails)
    _set_refresh_cookie(response, settings, result.refresh_token)
    _no_store(response)
    return _body(result)


@router.get("/config", response_model=AuthConfigOut)
def auth_config(settings: AppSettings) -> AuthConfigOut:
    """Public: which account-recovery features this server can actually perform."""
    return AuthConfigOut(
        password_reset_available=settings.email_enabled,
        email_verification_available=settings.email_enabled,
        email_verification_required=settings.email_verification_required,
    )


@router.post(
    "/password-reset/request",
    response_model=AcceptedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    mailer: Mailer,
) -> AcceptedOut:
    """E-mail a one-time reset link. The answer is identical for every address."""
    message = recovery.request_password_reset(
        db, settings, email=payload.email, context=RequestContext.from_request(request)
    )
    _send_after_response(background, mailer, (message,) if message else ())
    _no_store(response)
    return AcceptedOut()


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def password_reset_confirm(
    payload: PasswordResetConfirmRequest,
    request: Request,
    background: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    mailer: Mailer,
) -> Response:
    """Set a new password with a reset link. Ends every session; sign in again afterwards."""
    notice = recovery.confirm_password_reset(
        db,
        settings,
        token=payload.token,
        new_password=payload.new_password,
        context=RequestContext.from_request(request),
    )
    _send_after_response(background, mailer, (notice,))
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})


@router.post(
    "/email-verification/request",
    response_model=AcceptedOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def email_verification_request(
    payload: EmailVerificationRequest,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    db: DbSession,
    settings: AppSettings,
    mailer: Mailer,
) -> AcceptedOut:
    """E-mail a (new) confirmation link. Public, so someone who cannot sign in yet can ask."""
    message = recovery.request_email_verification(
        db, settings, email=payload.email, context=RequestContext.from_request(request)
    )
    _send_after_response(background, mailer, (message,) if message else ())
    _no_store(response)
    return AcceptedOut()


@router.post("/email-verification/confirm", status_code=status.HTTP_204_NO_CONTENT)
def email_verification_confirm(
    payload: EmailVerificationConfirmRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> Response:
    recovery.confirm_email_verification(
        db, settings, token=payload.token, context=RequestContext.from_request(request)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})


def _account(db: DbSession, principal: CurrentPrincipal) -> User:
    user = users.get_by_id(db, principal.user_id)
    if user is None:  # pragma: no cover - the principal was just loaded from this row
        raise UnauthenticatedError("Invalid or expired access token")
    return user


@router.get("/mfa", response_model=MfaStatusOut)
def mfa_status(db: DbSession, principal: CurrentPrincipal) -> MfaStatusOut:
    return mfa.status(db, principal.user_id)


@router.post("/mfa/enroll", response_model=MfaEnrollOut)
def mfa_enroll(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    principal: CurrentPrincipal,
) -> MfaEnrollOut:
    """Issue a new authenticator secret (shown once). It is inactive until confirmed."""
    _no_store(response)
    return mfa.begin_enrollment(
        db, settings, _account(db, principal), context=RequestContext.from_request(request)
    )


@router.post("/mfa/activate", response_model=MfaRecoveryCodesOut)
def mfa_activate(
    payload: MfaCodeRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    principal: CurrentPrincipal,
) -> MfaRecoveryCodesOut:
    """Confirm enrolment with a code from the app. Returns the recovery codes once."""
    _no_store(response)
    codes = mfa.activate(
        db,
        settings,
        _account(db, principal),
        payload.code,
        context=RequestContext.from_request(request),
    )
    return MfaRecoveryCodesOut(recovery_codes=codes)


@router.post("/mfa/disable", status_code=status.HTTP_204_NO_CONTENT)
def mfa_disable(
    payload: MfaProofRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
    principal: CurrentPrincipal,
) -> Response:
    mfa.disable(
        db,
        settings,
        _account(db, principal),
        password=payload.password,
        code=payload.code,
        context=RequestContext.from_request(request),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/mfa/recovery-codes", response_model=MfaRecoveryCodesOut)
def mfa_recovery_codes(
    payload: MfaProofRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    principal: CurrentPrincipal,
) -> MfaRecoveryCodesOut:
    """Replace every recovery code with ten new ones (the old ones stop working)."""
    _no_store(response)
    codes = mfa.regenerate_recovery_codes(
        db,
        settings,
        _account(db, principal),
        password=payload.password,
        code=payload.code,
        context=RequestContext.from_request(request),
    )
    return MfaRecoveryCodesOut(recovery_codes=codes)
