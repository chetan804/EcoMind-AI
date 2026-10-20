"""Auth endpoints, mounted at ``/api/v1/auth``."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.api.deps import AppSettings, DbSession
from app.core.config import Settings
from app.core.exceptions import AppError, error_response
from app.modules.audit.service import RequestContext
from app.modules.auth import service
from app.modules.auth.dependencies import (
    CurrentPrincipal,
    require_csrf_header,
)
from app.modules.auth.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    UserOut,
)

router = APIRouter()

REFRESH_COOKIE = "ecomind_refresh"
# The cookie is only ever sent to the auth endpoints, never with ordinary API calls.
REFRESH_COOKIE_PATH = "/api/v1/auth"


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
        ),
    )


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
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
    _set_refresh_cookie(response, settings, result.refresh_token)
    _no_store(response)
    return _body(result)


@router.post("/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> AuthResponse:
    result = service.login(
        db,
        settings,
        email=payload.email,
        password=payload.password,
        context=RequestContext.from_request(request),
    )
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
    )


@router.post("/change-password", response_model=AuthResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    principal: CurrentPrincipal,
    db: DbSession,
    settings: AppSettings,
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
    _set_refresh_cookie(response, settings, result.refresh_token)
    _no_store(response)
    return _body(result)
