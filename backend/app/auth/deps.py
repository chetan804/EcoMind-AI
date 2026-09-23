"""Request dependencies: authentication, organization context, permissions.

The organization context is resolved per request from the ``X-Org-Id`` header
(falling back to the user's default membership). While active, the session's
tenant filter scopes every ORM SELECT to that organization — see
app/core/db.py.
"""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from app.auth.models import User
from app.auth.rbac import PERMISSIONS
from app.auth.service import role_permissions_for
from app.core.db import AsyncSession, get_session, tenant_context
from app.core.errors import AuthError, ForbiddenError
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.orgs.models import Organization, OrgMembership

log = get_logger("auth")
bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise AuthError("Authentication required.")
    payload = decode_access_token(credentials.credentials)
    request.state.user_id = payload["sub"]
    user = (
        await session.execute(select(User).where(User.id == uuid.UUID(payload["sub"])))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthError("Account not found or inactive.")
    return user


@dataclass
class AuthContext:
    user: User
    session: AsyncSession
    org: Organization | None = None
    role_code: str | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)

    @property
    def org_id(self) -> uuid.UUID:
        if self.org is None:
            raise ForbiddenError("This action requires an organization context.")
        return self.org.id

    @property
    def is_platform_admin(self) -> bool:
        return self.user.is_platform_admin

    def has_perm(self, code: str) -> bool:
        return code in self.permissions

    def require_perm(self, code: str) -> None:
        if not self.has_perm(code):
            raise ForbiddenError(
                "You do not have permission to perform this action.",
                details={"required_permission": code},
            )

    def ensure_perm(self, code_all: str, code_own: str, owner_id: uuid.UUID | None) -> None:
        """Own-scope check: org-wide permission OR the resource belongs to the user."""
        if self.has_perm(code_all):
            return
        if self.has_perm(code_own) and owner_id == self.user.id:
            return
        raise ForbiddenError("You do not have permission to access this resource.")


async def _resolve_org(
    session: AsyncSession, user: User, requested_org: str | None
) -> Organization | None:
    if requested_org:
        try:
            org_id = uuid.UUID(requested_org)
            q = select(Organization).where(Organization.id == org_id)
        except ValueError:
            q = select(Organization).where(Organization.slug == requested_org)
        if user.is_platform_admin:
            org = (await session.execute(q)).scalar_one_or_none()
        else:
            org = (
                await session.execute(
                    q.join(OrgMembership, OrgMembership.organization_id == Organization.id).where(
                        OrgMembership.user_id == user.id,
                        OrgMembership.is_active.is_(True),
                    )
                )
            ).scalar_one_or_none()
        if org is None:
            raise ForbiddenError("You are not a member of the requested organization.")
        return org

    # default membership
    row = (
        await session.execute(
            select(Organization)
            .join(OrgMembership, OrgMembership.organization_id == Organization.id)
            .where(
                OrgMembership.user_id == user.id,
                OrgMembership.is_active.is_(True),
                OrgMembership.is_default.is_(True),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        row = (
            await session.execute(
                select(Organization)
                .join(OrgMembership, OrgMembership.organization_id == Organization.id)
                .where(OrgMembership.user_id == user.id, OrgMembership.is_active.is_(True))
                .limit(1)
            )
        ).scalar_one_or_none()
    return row


async def build_auth_context(
    request: Request,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    requested_org = request.headers.get("X-Org-Id")
    org = await _resolve_org(session, user, requested_org)

    if org is None:
        ctx = AuthContext(
            user=user,
            session=session,
            permissions=frozenset(PERMISSIONS if user.is_platform_admin else []),
        )
        yield ctx
        return

    if user.is_platform_admin:
        role_code, perms = "platform_admin", frozenset(PERMISSIONS)
    else:
        membership = (
            await session.execute(
                select(OrgMembership).where(
                    OrgMembership.user_id == user.id,
                    OrgMembership.organization_id == org.id,
                    OrgMembership.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        if membership is None:
            raise ForbiddenError("You are not a member of the requested organization.")
        role_code = membership.role_code
        perms = frozenset(await role_permissions_for(session, role_code))

    ctx = AuthContext(user=user, session=session, org=org, role_code=role_code, permissions=perms)
    with ExitStack() as stack:
        if org is not None:
            stack.enter_context(tenant_context(session, org.id))
        yield ctx


AuthCtx = Annotated[AuthContext, Depends(build_auth_context)]
DbSession = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def require_perm(code: str):
    """Dependency factory: `Depends(require_perm("route:generate"))`."""

    async def _check(ctx: AuthCtx) -> AuthContext:
        ctx.require_perm(code)
        return ctx

    return _check
