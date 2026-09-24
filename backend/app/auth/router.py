"""Auth endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select

from app.auth.deps import CurrentUser, DbSession
from app.auth.schemas import (
    AuthResponse,
    ForgotPasswordIn,
    LoginIn,
    MeOut,
    MessageOut,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    TokenPair,
)
from app.auth.service import (
    authenticate,
    consume_password_reset,
    create_password_reset,
    issue_token_pair,
    load_memberships,
    register,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.core.config import settings
from app.core.rate_limit import client_ip, rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


async def _auth_response(session, user, request) -> AuthResponse:
    access, refresh = await issue_token_pair(
        session,
        user,
        user_agent=request.headers.get("user-agent"),
        ip=client_ip(request),
    )
    await session.commit()
    memberships = await load_memberships(session, user)
    me = MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_active=user.is_active,
        email_verified_at=user.email_verified_at,
        locale=user.locale,
        created_at=user.created_at,
        is_platform_admin=user.is_platform_admin,
        memberships=memberships,
    )
    return AuthResponse(
        tokens=TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=settings.access_token_minutes * 60,
        ),
        user=me,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit("auth"))])
async def register_endpoint(body: RegisterIn, request: Request, session: DbSession):
    user = await register(
        session,
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        phone=body.phone,
    )
    # Optional immediate citizen signup to an open organization.
    if body.join_org_slug:
        from app.orgs.service import join_organization_as_citizen

        await join_organization_as_citizen(session, user=user, slug=body.join_org_slug)
    await session.commit()
    return await _auth_response(session, user, request)


@router.post("/login", response_model=AuthResponse, dependencies=[Depends(rate_limit("auth"))])
async def login_endpoint(body: LoginIn, request: Request, session: DbSession):
    user = await authenticate(session, email=body.email, password=body.password)
    await session.commit()
    return await _auth_response(session, user, request)


@router.post("/refresh", response_model=TokenPair, dependencies=[Depends(rate_limit("auth"))])
async def refresh_endpoint(body: RefreshIn, request: Request, session: DbSession):
    user, access, refresh = await rotate_refresh_token(
        session, body.refresh_token, user_agent=request.headers.get("user-agent"), ip=client_ip(request)
    )
    await session.commit()
    return TokenPair(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.access_token_minutes * 60,
    )


@router.post("/logout", response_model=MessageOut)
async def logout_endpoint(body: RefreshIn, session: DbSession):
    await revoke_refresh_token(session, body.refresh_token)
    await session.commit()
    return MessageOut(message="Logged out.")


@router.get("/me", response_model=MeOut)
async def me_endpoint(user: CurrentUser, session: DbSession):
    memberships = await load_memberships(session, user)
    return MeOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_active=user.is_active,
        email_verified_at=user.email_verified_at,
        locale=user.locale,
        created_at=user.created_at,
        is_platform_admin=user.is_platform_admin,
        memberships=memberships,
    )


@router.post("/forgot-password", response_model=MessageOut, dependencies=[Depends(rate_limit("auth"))])
async def forgot_password_endpoint(body: ForgotPasswordIn, request: Request, session: DbSession):
    token = await create_password_reset(session, body.email)
    await session.commit()
    if token:
        # Development without SMTP: the token is logged server-side only.
        # Production configures an email transport; the token is never returned by the API.
        from app.core.logging import get_logger

        get_logger("auth").info("password_reset_requested", email=body.email)
    return MessageOut(message="If that account exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageOut, dependencies=[Depends(rate_limit("auth"))])
async def reset_password_endpoint(body: ResetPasswordIn, session: DbSession):
    await consume_password_reset(session, body.token, body.new_password)
    await session.commit()
    return MessageOut(message="Password updated. Please log in again.")


@router.get("/public/organizations")
async def public_organizations(session: DbSession):
    """Organizations open for citizen signup (used by the registration flow)."""
    from app.orgs.models import Organization

    orgs = (
        await session.execute(
            select(Organization.slug, Organization.name, Organization.is_demo).where(
                Organization.allow_citizen_signup.is_(True),
                Organization.status == "active",
            ).order_by(Organization.name)
        )
    ).all()
    return {"items": [{"slug": s, "name": n, "is_demo": d} for s, n, d in orgs]}
