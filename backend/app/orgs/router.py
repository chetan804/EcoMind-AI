"""Organization, unit, zone, member and invitation endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select

from app.audit.service import record as audit
from app.auth.deps import AuthCtx, DbSession, require_perm
from app.core.errors import ForbiddenError, NotFoundError
from app.core.pagination import Page, page_params
from app.orgs.schemas import (
    InviteAccept,
    InviteCreate,
    InviteOut,
    MemberOut,
    MemberUpdate,
    OrganizationCreate,
    OrganizationOut,
    OrganizationUpdate,
    UnitCreate,
    UnitOut,
    ZoneCreate,
    ZoneOut,
)
from app.orgs.service import (
    accept_invitation,
    create_invitation,
    create_organization,
    create_unit,
    create_zone,
    join_organization_as_citizen,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _org_out(org) -> OrganizationOut:
    return OrganizationOut.model_validate(org)


@router.post("", response_model=OrganizationOut, status_code=status.HTTP_201_CREATED)
async def create_organization_endpoint(body: OrganizationCreate, ctx: AuthCtx, session: DbSession):
    """Self-service organization creation. The creator becomes org admin."""
    from app.core.db import unscoped

    with unscoped(session):  # organizations are platform-level rows
        org = await create_organization(
            session,
            name=body.name,
            slug=body.slug,
            org_type=body.org_type,
            creator_user_id=ctx.user.id,
            timezone=body.timezone,
            city=body.city,
            country=body.country,
            contact_email=body.contact_email,
        )
        await audit(
            session,
            action="organization.create",
            resource_type="organization",
            resource_id=org.id,
            organization_id=org.id,
            actor_user_id=ctx.user.id,
            actor_label=ctx.user.email,
            after={"name": org.name, "slug": org.slug, "org_type": org.org_type},
        )
    await session.commit()
    return _org_out(org)


@router.get("/mine", response_model=list[OrganizationOut])
async def my_organizations(ctx: AuthCtx, session: DbSession):
    from app.core.db import unscoped

    from app.orgs.models import OrgMembership

    with unscoped(session):
        orgs = (
            await session.execute(
                select(Organization)
                .join(OrgMembership, OrgMembership.organization_id == Organization.id)
                .where(OrgMembership.user_id == ctx.user.id, OrgMembership.is_active.is_(True))
                .order_by(OrgMembership.is_default.desc(), Organization.name)
            )
        ).scalars().all()
    return [_org_out(o) for o in orgs]


@router.get("/current", response_model=OrganizationOut)
async def current_organization(ctx: AuthCtx):
    if ctx.org is None:
        raise NotFoundError("No organization context. Create or join an organization first.")
    return _org_out(ctx.org)


@router.patch("/current", response_model=OrganizationOut, dependencies=[Depends(require_perm("org:update"))])
async def update_organization(body: OrganizationUpdate, ctx: AuthCtx, session: DbSession):
    org = ctx.org
    before = {"name": org.name, "settings": org.settings}
    for field_name, value in body.model_dump(exclude_unset=True).items():
        setattr(org, field_name, value)
    await audit(
        session,
        action="organization.update",
        resource_type="organization",
        resource_id=org.id,
        organization_id=org.id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        before=before,
        after={"name": org.name, "settings": org.settings},
    )
    await session.commit()
    return _org_out(org)


@router.post("/join/{slug}", response_model=OrganizationOut)
async def join_endpoint(slug: str, ctx: AuthCtx, session: DbSession):
    org = await join_organization_as_citizen(session, user=ctx.user, slug=slug)
    await session.commit()
    return _org_out(org)


# --- Members ----------------------------------------------------------------


@router.get("/current/members", response_model=Page, dependencies=[Depends(require_perm("user:read"))])
async def list_members(ctx: AuthCtx, session: DbSession, page: int = 1, page_size: int = 50):
    from app.orgs.models import OrgMembership

    q = (
        select(OrgMembership)
        .where(OrgMembership.organization_id == ctx.org_id)
        .order_by(OrgMembership.created_at)
    )
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    memberships = (
        await session.execute(q.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    user_ids = [m.user_id for m in memberships]
    users = {}
    if user_ids:
        from app.auth.models import User

        rows = (await session.execute(select(User).where(User.id.in_(user_ids)))).scalars().all()
        users = {u.id: u for u in rows}
    items = [
        MemberOut(
            user_id=m.user_id,
            email=users[m.user_id].email if m.user_id in users else "unknown",
            full_name=users[m.user_id].full_name if m.user_id in users else "unknown",
            role_code=m.role_code,
            is_active=m.is_active,
            joined_at=m.created_at,
        ).model_dump()
        for m in memberships
    ]
    return Page.build(items, total, page, page_size)


@router.patch("/current/members/{user_id}", dependencies=[Depends(require_perm("user:manage"))])
async def update_member(user_id: uuid.UUID, body: MemberUpdate, ctx: AuthCtx, session: DbSession):
    from app.auth.rbac import ROLES
    from app.orgs.models import OrgMembership

    if body.role_code and body.role_code not in ROLES:
        from app.core.errors import ValidationApiError

        raise ValidationApiError("Unknown role code.")
    m = (
        await session.execute(
            select(OrgMembership).where(
                OrgMembership.organization_id == ctx.org_id,
                OrgMembership.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if m is None:
        raise NotFoundError("Member not found.")
    if user_id == ctx.user.id and body.is_active is False:
        raise ForbiddenError("You cannot deactivate your own membership.")
    before = {"role_code": m.role_code, "is_active": m.is_active}
    if body.role_code is not None:
        m.role_code = body.role_code
    if body.is_active is not None:
        m.is_active = body.is_active
    await audit(
        session,
        action="member.update",
        resource_type="org_membership",
        resource_id=user_id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        before=before,
        after={"role_code": m.role_code, "is_active": m.is_active},
    )
    await session.commit()
    return {"ok": True}


# --- Invitations ------------------------------------------------------------


@router.post("/current/invitations", response_model=InviteOut, status_code=201,
             dependencies=[Depends(require_perm("user:invite"))])
async def create_invite(body: InviteCreate, ctx: AuthCtx, session: DbSession):
    invite, token = await create_invitation(
        session,
        organization_id=ctx.org_id,
        email=body.email,
        role_code=body.role_code,
        invited_by=ctx.user.id,
    )
    await audit(
        session,
        action="member.invite",
        resource_type="org_invitation",
        resource_id=invite.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        after={"email": body.email, "role_code": body.role_code},
    )
    await session.commit()
    return InviteOut(
        id=invite.id,
        email=invite.email,
        role_code=invite.role_code,
        expires_at=invite.expires_at,
        invite_token=token,
    )


@router.post("/invitations/accept")
async def accept_invite(body: InviteAccept, ctx: AuthCtx, session: DbSession):
    invite = await accept_invitation(session, token=body.token, user=ctx.user)
    await audit(
        session,
        action="member.invite_accept",
        resource_type="org_invitation",
        resource_id=invite.id,
        organization_id=invite.organization_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
    )
    await session.commit()
    return {"ok": True, "organization_id": str(invite.organization_id)}


# --- Units & Zones ------------------------------------------------------------


@router.post("/current/units", response_model=UnitOut, status_code=201,
             dependencies=[Depends(require_perm("unit:manage"))])
async def create_unit_endpoint(body: UnitCreate, ctx: AuthCtx, session: DbSession):
    unit = await create_unit(
        session, ctx.org_id, name=body.name, code=body.code, description=body.description
    )
    await audit(
        session,
        action="unit.create",
        resource_type="operational_unit",
        resource_id=unit.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        after={"name": unit.name, "code": unit.code},
    )
    await session.commit()
    return UnitOut.model_validate(unit)


@router.get("/current/units", response_model=list[UnitOut])
async def list_units(ctx: AuthCtx, session: DbSession):
    from app.orgs.models import OperationalUnit

    units = (
        await session.execute(
            select(OperationalUnit)
            .where(OperationalUnit.organization_id == ctx.org_id)
            .order_by(OperationalUnit.name)
        )
    ).scalars().all()
    return [UnitOut.model_validate(u) for u in units]


@router.post("/current/zones", response_model=ZoneOut, status_code=201,
             dependencies=[Depends(require_perm("zone:manage"))])
async def create_zone_endpoint(body: ZoneCreate, ctx: AuthCtx, session: DbSession):
    zone = await create_zone(
        session,
        ctx.org_id,
        name=body.name,
        code=body.code,
        boundary=body.boundary,
        unit_id=body.unit_id,
        color_hex=body.color_hex,
    )
    await audit(
        session,
        action="zone.create",
        resource_type="zone",
        resource_id=zone.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        after={"name": zone.name, "code": zone.code},
    )
    await session.commit()
    return ZoneOut(
        id=zone.id,
        name=zone.name,
        code=zone.code,
        unit_id=zone.unit_id,
        color_hex=zone.color_hex,
        boundary=zone.boundary,
        centroid_lat=zone.centroid_lat,
        centroid_lng=zone.centroid_lng,
        created_at=zone.created_at,
    )


@router.get("/current/zones", response_model=list[ZoneOut])
async def list_zones(ctx: AuthCtx, session: DbSession):
    from app.orgs.models import Zone

    zones = (
        await session.execute(
            select(Zone).where(Zone.organization_id == ctx.org_id).order_by(Zone.name)
        )
    ).scalars().all()
    return [
        ZoneOut(
            id=z.id,
            name=z.name,
            code=z.code,
            unit_id=z.unit_id,
            color_hex=z.color_hex,
            boundary=z.boundary,
            centroid_lat=z.centroid_lat,
            centroid_lng=z.centroid_lng,
            created_at=z.created_at,
        )
        for z in zones
    ]
