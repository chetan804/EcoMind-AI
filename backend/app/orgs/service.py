"""Organizations: creation (self-service onboarding), membership, zones."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.core.db import AsyncSession, utcnow
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.core.gis import parse_polygon_geojson, polygon_bbox, polygon_centroid
from app.core.logging import get_logger
from app.core.security import hash_token, new_opaque_token
from app.orgs.models import (
    OperationalUnit,
    OrgInvitation,
    OrgMembership,
    OrgUsageCounters,
    Organization,
    Zone,
)
from app.waste.models import WasteCategory

log = get_logger("orgs")

DEFAULT_CATEGORIES = [
    ("mixed", "Mixed Waste", "#64748b", "trash-2", "General household waste collected together."),
    ("recyclable", "Recyclables", "#3b82f6", "rotate-ccw", "Paper, plastics, glass and metals suitable for recycling."),
    ("organic", "Organic / Wet Waste", "#22c55e", "leaf", "Food and garden waste suitable for composting."),
    ("hazardous", "Hazardous", "#ef4444", "alert-triangle", "Batteries, chemicals, medical waste requiring special handling."),
    ("e_waste", "E-Waste", "#a855f7", "cpu", "Electronic equipment and components."),
    ("construction", "Construction Debris", "#d97706", "hard-hat", "Inert construction and demolition material."),
]

DEFAULT_ALERT_RULES = [
    ("Bin fill above 85%", "fill_pct", "gte", 85, "high", 60),
    ("High temperature (fire risk)", "temperature_c", "gt", 55, "critical", 30),
    ("Device battery low", "battery_pct", "lt", 15, "warning", 1440),
]


async def slug_exists(session: AsyncSession, slug: str) -> bool:
    return (
        await session.execute(select(Organization.id).where(Organization.slug == slug))
    ).scalar_one_or_none() is not None


async def create_organization(
    session: AsyncSession, *, name: str, slug: str, org_type: str, creator_user_id: uuid.UUID,
    timezone: str = "UTC", city: str | None = None, country: str | None = None,
    contact_email: str | None = None, is_demo: bool = False,
) -> Organization:
    if await slug_exists(session, slug):
        raise ConflictError("This organization slug is already taken.")
    org = Organization(
        name=name,
        slug=slug,
        org_type=org_type,
        timezone=timezone,
        city=city,
        country=country,
        contact_email=contact_email,
        is_demo=is_demo,
    )
    session.add(org)
    await session.flush()

    session.add(
        OrgMembership(
            user_id=creator_user_id, organization_id=org.id, role_code="org_admin", is_default=True
        )
    )
    session.add(OrgUsageCounters(organization_id=org.id, updated_at=utcnow()))
    # Sensible starter configuration so the org is immediately operable.
    for i, (code, nm, color, icon, guidance) in enumerate(DEFAULT_CATEGORIES):
        session.add(
            WasteCategory(
                organization_id=org.id,
                code=code,
                name=nm,
                color_hex=color,
                icon=icon,
                default_handling_guidance=guidance,
                sort_order=(i + 1) * 10,
            )
        )
    from app.iot.models import AlertRule, AlertRuleMetric, AlertSeverity

    for name_r, metric, op, threshold, severity, cooldown in DEFAULT_ALERT_RULES:
        session.add(
            AlertRule(
                organization_id=org.id,
                name=name_r,
                metric=AlertRuleMetric(metric),
                operator=op,
                threshold=threshold,
                severity=AlertSeverity(severity),
                cooldown_minutes=cooldown,
            )
        )
    return org


async def join_organization_as_citizen(session: AsyncSession, *, user, slug: str) -> Organization:
    org = (
        await session.execute(select(Organization).where(Organization.slug == slug))
    ).scalar_one_or_none()
    if org is None:
        raise NotFoundError("Organization not found.")
    if not org.allow_citizen_signup:
        raise ForbiddenError("This organization does not accept public signups.")
    existing = (
        await session.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id, OrgMembership.organization_id == org.id
            )
        )
    ).scalar_one_or_none()
    if existing:
        return org
    has_default = (
        await session.execute(
            select(func.count()).select_from(OrgMembership).where(
                OrgMembership.user_id == user.id, OrgMembership.is_default.is_(True)
            )
        )
    ).scalar_one()
    session.add(
        OrgMembership(
            user_id=user.id,
            organization_id=org.id,
            role_code="citizen",
            is_default=has_default == 0,
        )
    )
    return org


async def create_unit(session: AsyncSession, org_id: uuid.UUID, *, name: str, code: str, description: str | None):
    dupe = (
        await session.execute(
            select(OperationalUnit.id).where(
                OperationalUnit.organization_id == org_id, OperationalUnit.code == code
            )
        )
    ).scalar_one_or_none()
    if dupe:
        raise ConflictError("Unit code already exists in this organization.")
    unit = OperationalUnit(organization_id=org_id, name=name, code=code, description=description)
    session.add(unit)
    return unit


async def create_zone(
    session: AsyncSession, org_id: uuid.UUID, *, name: str, code: str, boundary: dict,
    unit_id: uuid.UUID | None = None, color_hex: str = "#10b981",
) -> Zone:
    polygon = parse_polygon_geojson(boundary)  # raises GeoValidationError -> 422
    dupe = (
        await session.execute(
            select(Zone.id).where(Zone.organization_id == org_id, Zone.code == code)
        )
    ).scalar_one_or_none()
    if dupe:
        raise ConflictError("Zone code already exists in this organization.")
    lat, lng = polygon_centroid(polygon)
    bbox = polygon_bbox(polygon)
    zone = Zone(
        organization_id=org_id,
        name=name,
        code=code,
        unit_id=unit_id,
        color_hex=color_hex,
        boundary=boundary,
        centroid_lat=lat,
        centroid_lng=lng,
        bbox_min_lat=bbox.min_lat,
        bbox_min_lng=bbox.min_lng,
        bbox_max_lat=bbox.max_lat,
        bbox_max_lng=bbox.max_lng,
    )
    session.add(zone)
    return zone


async def create_invitation(
    session: AsyncSession, *, organization_id: uuid.UUID, email: str, role_code: str, invited_by: uuid.UUID
) -> tuple[OrgInvitation, str]:
    from datetime import timedelta

    from app.core.config import settings

    token = new_opaque_token("emi")
    invite = OrgInvitation(
        organization_id=organization_id,
        email=email.strip().lower(),
        role_code=role_code,
        token_hash=hash_token(token),
        expires_at=utcnow() + timedelta(days=7),
        invited_by=invited_by,
    )
    session.add(invite)
    return invite, token


async def accept_invitation(session: AsyncSession, *, token: str, user) -> OrgInvitation:
    invite = (
        await session.execute(
            select(OrgInvitation).where(OrgInvitation.token_hash == hash_token(token))
        )
    ).scalar_one_or_none()
    if invite is None or invite.revoked or invite.accepted_at is not None:
        raise NotFoundError("Invitation not found or already used.")
    if invite.expires_at < utcnow():
        raise ForbiddenError("This invitation has expired.")
    existing = (
        await session.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id,
                OrgMembership.organization_id == invite.organization_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        session.add(
            OrgMembership(
                user_id=user.id,
                organization_id=invite.organization_id,
                role_code=invite.role_code,
            )
        )
    invite.accepted_at = utcnow()
    return invite
