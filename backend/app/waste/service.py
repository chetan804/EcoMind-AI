"""Waste report lifecycle service."""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import func, select

from app.audit.service import record as audit
from app.core.config import settings
from app.core.db import AsyncSession, utcnow
from app.core.errors import ForbiddenError, NotFoundError, ValidationApiError
from app.core.gis import haversine_m, parse_polygon_geojson, point_in_polygon
from app.core.logging import get_logger
from app.core.rate_limit import limiter
from app.notifications.service import notify_user
from app.rewards.models import RewardLedger, RewardReason
from app.waste.models import ReportSeverity, ReportSource, ReportStatus, WasteReport, WasteReportEvent

log = get_logger("waste")

VALID_TRANSITIONS = {
    "submitted": {"triaged", "in_progress", "resolved", "rejected"},
    "triaged": {"in_progress", "resolved", "rejected"},
    "in_progress": {"resolved", "rejected"},
    "resolved": {"closed"},
    "rejected": {"closed"},
    "closed": set(),
}

SEVERITY_ORDER = [ReportSeverity.low, ReportSeverity.medium, ReportSeverity.high, ReportSeverity.urgent]


def anon_fingerprint(ip: str) -> str:
    """Salted, one-way per-IP fingerprint for anonymous abuse limits."""
    return hashlib.sha256((settings.effective_secret_key() + "|anon|" + ip).encode()).hexdigest()[:48]


async def _find_zone(session, org_id: uuid.UUID, lat: float, lng: float):
    from app.orgs.models import Zone

    zones = (
        await session.execute(select(Zone).where(Zone.organization_id == org_id))
    ).scalars().all()
    for zone in zones:
        if zone.bbox_min_lat <= lat <= zone.bbox_max_lat and zone.bbox_min_lng <= lng <= zone.bbox_max_lng:
            try:
                if point_in_polygon(lat, lng, parse_polygon_geojson(zone.boundary)):
                    return zone
            except Exception:
                continue
    return None


async def create_report(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    reporter_user_id: uuid.UUID | None,
    description: str | None,
    category_guess: str | None,
    latitude: float,
    longitude: float,
    location_accuracy_m: float | None,
    address: str | None,
    source: ReportSource,
    photo_media_id: uuid.UUID | None,
    is_anonymous: bool = False,
    contact: str | None = None,
    anon_ip: str | None = None,
    reporter_name: str | None = None,
):
    if is_anonymous and reporter_user_id is None:
        if anon_ip is None:
            raise ValidationApiError("Anonymous submissions require a client IP.")
        fp = anon_fingerprint(anon_ip)
        allowed, _ = limiter.allow("anon_report", fp, 5)  # 5 anonymous reports / hour-ish bucket
        if not allowed:
            raise ForbiddenError("Too many anonymous reports from this network. Please try again later.")
    else:
        fp = None
        if reporter_user_id is None:
            raise ValidationApiError("Report must be authenticated or explicitly anonymous.")

    zone = await _find_zone(session, organization_id, latitude, longitude)

    report = WasteReport(
        organization_id=organization_id,
        reporter_user_id=None if is_anonymous else reporter_user_id,
        is_anonymous=is_anonymous,
        anon_fingerprint=fp,
        contact=contact,
        description=description,
        category_guess=category_guess,
        photo_media_id=photo_media_id,
        latitude=latitude,
        longitude=longitude,
        location_accuracy_m=location_accuracy_m,
        address=address,
        zone_id=zone.id if zone else None,
        status=ReportStatus.submitted,
        source=source,
    )
    session.add(report)
    await session.flush()
    session.add(
        WasteReportEvent(
            organization_id=organization_id,
            report_id=report.id,
            event_type="created",
            actor_user_id=reporter_user_id,
            to_status=ReportStatus.submitted.value,
            note=description,
            created_at=utcnow(),
        )
    )
    if reporter_user_id and not is_anonymous:
        session.add(
            RewardLedger(
                organization_id=organization_id,
                user_id=reporter_user_id,
                points=10,
                reason=RewardReason.report_submitted,
                description="Waste report submitted",
                reference_type="waste_report",
                reference_id=report.id,
                awarded_at=utcnow(),
            )
        )
    return report


async def attach_inference(session, report: WasteReport, inference) -> None:
    report.ai_inference_id = inference.id
    session.add(
        WasteReportEvent(
            organization_id=report.organization_id,
            report_id=report.id,
            event_type="ai_classified",
            note=f"provider={inference.provider} status={inference.status} confidence={inference.confidence}",
            created_at=utcnow(),
        )
    )


async def get_report(session, organization_id: uuid.UUID, report_id: uuid.UUID) -> WasteReport:
    report = (
        await session.execute(
            select(WasteReport).where(
                WasteReport.id == report_id, WasteReport.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()
    if report is None:
        raise NotFoundError("Report not found.")
    return report


async def update_status(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    report_id: uuid.UUID,
    actor_user_id: uuid.UUID | None,
    actor_label: str,
    new_status: str,
    note: str | None,
    severity: str | None = None,
    confirmed_category_id: uuid.UUID | None = None,
    resolution_notes: str | None = None,
) -> WasteReport:
    report = await get_report(session, organization_id, report_id)
    try:
        target = ReportStatus(new_status)
    except ValueError as e:
        raise ValidationApiError(f"Unknown status '{new_status}'.") from e
    allowed = VALID_TRANSITIONS.get(report.status.value, set())
    if target.value not in allowed and target != report.status:
        raise ValidationApiError(
            f"Cannot transition from '{report.status.value}' to '{target.value}'.",
            details={"allowed": sorted(allowed)},
        )
    before = {"status": report.status.value, "severity": report.severity.value}
    from_status = report.status
    report.status = target
    if severity:
        try:
            report.severity = ReportSeverity(severity)
        except ValueError as e:
            raise ValidationApiError(f"Unknown severity '{severity}'.") from e
    if confirmed_category_id:
        report.confirmed_category_id = confirmed_category_id
    if resolution_notes is not None:
        report.resolution_notes = resolution_notes
    if target == ReportStatus.resolved:
        report.resolved_at = utcnow()
        if report.reporter_user_id:
            session.add(
                RewardLedger(
                    organization_id=organization_id,
                    user_id=report.reporter_user_id,
                    points=25,
                    reason=RewardReason.report_resolved,
                    description="Your report was resolved",
                    reference_type="waste_report",
                    reference_id=report.id,
                    awarded_at=utcnow(),
                )
            )
            await notify_user(
                session,
                user_id=report.reporter_user_id,
                organization_id=organization_id,
                category="report_update",
                title="Your report was resolved",
                body=resolution_notes or "Thank you for helping keep your community clean.",
                data={"report_id": str(report.id), "status": "resolved"},
            )
    session.add(
        WasteReportEvent(
            organization_id=organization_id,
            report_id=report.id,
            event_type="status_change",
            actor_user_id=actor_user_id,
            from_status=from_status.value,
            to_status=target.value,
            note=note,
            created_at=utcnow(),
        )
    )
    await audit(
        session,
        action="report.update_status",
        resource_type="waste_report",
        resource_id=report.id,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        before=before,
        after={"status": report.status.value, "severity": report.severity.value},
    )
    return report


async def assign(
    session: AsyncSession, *, organization_id: uuid.UUID, report_id: uuid.UUID,
    assignee_user_id: uuid.UUID, actor_user_id: uuid.UUID, actor_label: str,
) -> WasteReport:
    from app.orgs.models import OrgMembership

    member = (
        await session.execute(
            select(OrgMembership).where(
                OrgMembership.organization_id == organization_id,
                OrgMembership.user_id == assignee_user_id,
                OrgMembership.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if member is None:
        raise ValidationApiError("Assignee is not an active member of this organization.")
    report = await get_report(session, organization_id, report_id)
    report.assigned_to = assignee_user_id
    if report.status == ReportStatus.submitted:
        report.status = ReportStatus.in_progress
    session.add(
        WasteReportEvent(
            organization_id=organization_id,
            report_id=report.id,
            event_type="assigned",
            actor_user_id=actor_user_id,
            note=f"assigned to {assignee_user_id}",
            created_at=utcnow(),
        )
    )
    await notify_user(
        session,
        user_id=assignee_user_id,
        organization_id=organization_id,
        category="report_update",
        title="A waste report was assigned to you",
        body=report.description or "See details in the operations console.",
        data={"report_id": str(report.id)},
    )
    await audit(
        session,
        action="report.assign",
        resource_type="waste_report",
        resource_id=report.id,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        after={"assigned_to": str(assignee_user_id)},
    )
    return report


async def list_reports(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    viewer_user_id: uuid.UUID | None = None,
    read_all: bool,
    status: str | None = None,
    severity: str | None = None,
    zone_id: uuid.UUID | None = None,
    mine_only: bool = False,
    near_lat: float | None = None,
    near_lng: float | None = None,
    near_radius_m: float = 2000,
    limit: int = 25,
    offset: int = 0,
    order: str = "recent",
):
    q = select(WasteReport).where(WasteReport.organization_id == organization_id)
    if not read_all or mine_only:
        if viewer_user_id:
            q = q.where(WasteReport.reporter_user_id == viewer_user_id)
        else:
            q = q.where(WasteReport.reporter_user_id.is_(None))
    if status:
        q = q.where(WasteReport.status == status)
    if severity:
        q = q.where(WasteReport.severity == severity)
    if zone_id:
        q = q.where(WasteReport.zone_id == zone_id)
    if near_lat is not None and near_lng is not None:
        # Portable spatial pre-filter: bounding box, then exact haversine in SQL.
        deg_lat = near_radius_m / 111_320.0
        deg_lng = near_radius_m / (111_320.0 * max(0.01, abs(near_lat)))
        q = q.filter(
            WasteReport.latitude.between(near_lat - deg_lat, near_lat + deg_lat),
            WasteReport.longitude.between(near_lng - deg_lng, near_lng + deg_lng),
        )
    total = (await session.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    if order == "severity":
        from sqlalchemy import case

        sev_rank = case({sev.value: i for i, sev in enumerate(SEVERITY_ORDER)})
        q = q.order_by(sev_rank, WasteReport.created_at.desc())
    else:
        q = q.order_by(WasteReport.created_at.desc())
    items = (await session.execute(q.limit(limit).offset(offset))).scalars().all()
    if near_lat is not None and near_lng is not None:
        items = [r for r in items if haversine_m(near_lat, near_lng, r.latitude, r.longitude) <= near_radius_m]
    return items, total


async def report_timeline(session, organization_id: uuid.UUID, report_id: uuid.UUID):
    events = (
        await session.execute(
            select(WasteReportEvent)
            .where(
                WasteReportEvent.report_id == report_id,
                WasteReportEvent.organization_id == organization_id,
            )
            .order_by(WasteReportEvent.created_at)
        )
    ).scalars().all()
    return events
