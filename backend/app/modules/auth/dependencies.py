"""Request authentication and authorization dependencies used by every protected endpoint.

    @router.get("/things", dependencies=[Depends(require_permissions("things:read"))])

or, when the handler needs the caller::

    def handler(principal: Annotated[Principal, Depends(require_permissions("things:read"))]): ...

Authorization is deny-by-default and always decided on the server from the database: the access
token only proves *who* the caller is. Roles and permissions are re-read on every request, so a
deactivated account or a revoked role takes effect immediately rather than at token expiry.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import AppSettings, DbSession
from app.core.exceptions import ForbiddenError, UnauthenticatedError
from app.core.permissions import ensure_permissions
from app.core.security import CSRF_HEADER, CSRF_HEADER_VALUE, decode_access_token
from app.modules.auth import mfa
from app.modules.auth.errors import MfaEnrollmentRequiredError
from app.modules.users import repository as users

_bearer = HTTPBearer(auto_error=False, description="Short-lived access token from /auth/login")
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class Principal:
    user_id: uuid.UUID
    email: str
    full_name: str
    roles: frozenset[str]
    permissions: frozenset[str]
    email_verified: bool = False
    # A role of this person requires two-step verification and it is not active yet: the person
    # may only set it up (see ``ActivePrincipal`` and ``require_permissions``).
    mfa_enrollment_required: bool = False

    def has(self, permission: str) -> bool:
        return permission in self.permissions


def get_current_principal(
    db: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    if credentials is None:
        raise UnauthenticatedError("Authentication required", headers=_CHALLENGE)
    try:
        claims = decode_access_token(
            credentials.credentials,
            secret_key=settings.secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
        )
        user_id = uuid.UUID(str(claims["sub"]))
    except (UnauthenticatedError, ValueError, KeyError) as exc:
        raise UnauthenticatedError("Invalid or expired access token", headers=_CHALLENGE) from exc
    user = users.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise UnauthenticatedError("Invalid or expired access token", headers=_CHALLENGE)
    roles = frozenset(users.role_names(db, user.id))
    return Principal(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        roles=roles,
        permissions=frozenset(users.permission_codes(db, user.id)),
        email_verified=user.email_verified_at is not None,
        mfa_enrollment_required=mfa.enrollment_required(db, settings, user.id, roles),
    )


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


def _refuse_until_mfa_is_set_up(principal: Principal) -> None:
    if principal.mfa_enrollment_required:
        raise MfaEnrollmentRequiredError(
            "Your role requires two-step verification. Set it up under Settings, Security."
        )


def get_active_principal(principal: CurrentPrincipal) -> Principal:
    """Like ``get_current_principal`` but refuses people who still have to set up two-step
    verification. The account and two-step endpoints use the plain one so they remain reachable."""
    _refuse_until_mfa_is_set_up(principal)
    return principal


ActivePrincipal = Annotated[Principal, Depends(get_active_principal)]


def require_permissions(*required: str) -> Callable[[Principal], Principal]:
    """Dependency factory: the caller must hold *every* listed permission."""
    if not required:
        raise ValueError("require_permissions needs at least one permission")

    def dependency(principal: ActivePrincipal) -> Principal:
        ensure_permissions(principal.permissions, required)
        return principal

    return dependency


def require_any_permission(*accepted: str) -> Callable[[Principal], Principal]:
    """Dependency factory: the caller must hold *at least one* of the listed permissions.

    Use it where two permissions grant different scopes of the same operation (for example
    ``read_own`` / ``read_all``); the handler then decides the scope from ``principal.has(...)``.
    """
    if not accepted:
        raise ValueError("require_any_permission needs at least one permission")

    def dependency(principal: ActivePrincipal) -> Principal:
        if not any(principal.has(code) for code in accepted):
            # Same message as require_permissions: never reveal which permission was needed.
            raise ForbiddenError("You do not have permission to perform this action")
        return principal

    return dependency


def require_csrf_header(request: Request) -> None:
    """Guard for the cookie-authenticated endpoints (refresh, logout); see core/security.py."""
    if request.headers.get(CSRF_HEADER) != CSRF_HEADER_VALUE:
        raise ForbiddenError(f"Missing required {CSRF_HEADER} header")
