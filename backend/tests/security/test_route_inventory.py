"""Every API route is protected unless it is deliberately public (deny by default, checked mechanically)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from app.common.route_inventory import RouteInfo, inventory
from app.main import create_app
from app.modules.users.rbac import PERMISSIONS, ROLES
from tests.conftest import SettingsFactory

# Routes that need no access token, with the reason. Adding to this set is a security decision.
PUBLIC = {
    ("GET", "/health"): "liveness probe",
    ("GET", "/ready"): "readiness probe",
    ("POST", "/api/v1/auth/register"): "self-registration (always yields the citizen role)",
    ("POST", "/api/v1/auth/login"): "sign-in (rate limited and locked out per email)",
    ("POST", "/api/v1/auth/mfa/verify"): "second step of sign-in, needs the challenge token",
    ("POST", "/api/v1/auth/refresh"): "refresh cookie plus CSRF header",
    ("POST", "/api/v1/auth/logout"): "refresh cookie plus CSRF header",
    ("GET", "/api/v1/auth/config"): "tells the sign-in page which e-mail features are enabled",
    ("POST", "/api/v1/auth/password-reset/request"): (
        "same answer for every address; rate limited per address and per IP"
    ),
    ("POST", "/api/v1/auth/password-reset/confirm"): "needs the one-time token from the e-mail",
    ("POST", "/api/v1/auth/email-verification/request"): (
        "same answer for every address; rate limited per address and per IP"
    ),
    ("POST", "/api/v1/auth/email-verification/confirm"): "needs the one-time token from the e-mail",
}

# Routes open to any signed-in user without a named permission: each acts only on the caller's own
# account, or is non-sensitive reference data.
SIGNED_IN_ONLY = {
    ("GET", "/api/v1/auth/me"),
    ("POST", "/api/v1/auth/change-password"),
    ("GET", "/api/v1/auth/mfa"),
    ("POST", "/api/v1/auth/mfa/enroll"),
    ("POST", "/api/v1/auth/mfa/activate"),
    ("POST", "/api/v1/auth/mfa/disable"),
    ("POST", "/api/v1/auth/mfa/recovery-codes"),
    ("GET", "/api/v1/classification/model"),
}


@pytest.fixture
def routes(make_settings: SettingsFactory) -> list[RouteInfo]:
    app: FastAPI = create_app(make_settings())
    return inventory(app)


def test_the_inventory_is_not_silently_empty(routes: list[RouteInfo]) -> None:
    assert len(routes) >= 100


def test_only_the_listed_routes_are_public(routes: list[RouteInfo]) -> None:
    public = {(r.method, r.path) for r in routes if not r.requires_sign_in}
    assert public == set(PUBLIC)


def test_only_the_listed_routes_need_no_permission(routes: list[RouteInfo]) -> None:
    open_to_signed_in = {
        (r.method, r.path) for r in routes if r.requires_sign_in and not r.permissions
    }
    assert open_to_signed_in == SIGNED_IN_ONLY


def test_cookie_endpoints_require_the_csrf_header(routes: list[RouteInfo]) -> None:
    csrf = {(r.method, r.path) for r in routes if r.requires_csrf_header}
    assert csrf == {("POST", "/api/v1/auth/refresh"), ("POST", "/api/v1/auth/logout")}


def test_every_required_permission_exists_and_is_held_by_some_role(
    routes: list[RouteInfo],
) -> None:
    held = set().union(*(perms for _, perms in ROLES.values()))
    for route in routes:
        for permission in route.permissions:
            assert permission in PERMISSIONS, (route.path, permission)
            assert permission in held, (route.path, permission)
