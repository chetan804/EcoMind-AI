"""Waste report + category endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select

from app.ai.service import classify_waste_report
from app.auth.deps import AuthCtx, DbSession, require_perm
from app.core.errors import NotFoundError, ValidationApiError
from app.core.pagination import Page, page_params
from app.core.rate_limit import client_ip, rate_limit
from app.media.service import store_upload
from app.waste.models import WasteCategory
from app.waste.schemas import (
    ReportAssign,
    ReportCreate,
    ReportEventOut,
    ReportOut,
    ReportStatusUpdate,
)
from app.waste.service import (
    assign as assign_report,
    attach_inference,
    create_report,
    get_report,
    list_reports,
    report_timeline,
    update_status,
)

router = APIRouter(prefix="/waste", tags=["waste"])

_PARENT = {"reporter", "assigned"}


async def _report_out(session, r) -> dict:
    reporter_name = None
    assigned_name = None
    zone_name = None
    ai_category = ai_confidence = ai_is_sim = None
    from app.ai.models import AiInference
    from app.auth.models import User
    from app.orgs.models import Zone

    if r.reporter_user_id:
        u = (await session.execute(select(User.full_name).where(User.id == r.reporter_user_id))).scalar_one_or_none()
        reporter_name = u or None
    if r.assigned_to:
        u = (await session.execute(select(User.full_name).where(User.id == r.assigned_to))).scalar_one_or_none()
        assigned_name = u or None
    if r.zone_id:
        zone_name = (
            await session.execute(select(Zone.name).where(Zone.id == r.zone_id))
        ).scalar_one_or_none()
    if r.ai_inference_id:
        inf = (
            await session.execute(select(AiInference).where(AiInference.id == r.ai_inference_id))
        ).scalar_one_or_none()
        if inf:
            ai_category = (inf.output or {}).get("category")
            ai_confidence = inf.confidence
            ai_is_sim = inf.is_simulated
    out = ReportOut.model_validate(r).model_dump()
    out.update(
        reporter_name=reporter_name,
        assigned_to_name=assigned_name,
        zone_name=zone_name,
        ai_category=ai_category,
        ai_confidence=ai_confidence,
        ai_is_simulated=ai_is_sim,
    )
    return out


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit("write"))])
async def create_report_endpoint(
    ctx: AuthCtx,
    session: DbSession,
    body: ReportCreate,
):
    """Submit a waste report. Authenticated users; anonymous flow is separate."""
    if ctx.org is None:
        raise NotFoundError("No organization context. Join or create an organization first.")
    report = await create_report(
        session,
        organization_id=ctx.org_id,
        reporter_user_id=ctx.user.id,
        description=body.description,
        category_guess=body.category_guess,
        latitude=body.latitude,
        longitude=body.longitude,
        location_accuracy_m=body.location_accuracy_m,
        address=body.address,
        source="citizen_app" if ctx.role_code == "citizen" else "web",
        photo_media_id=body.photo_media_id,
        is_anonymous=False,
    )
    # AI classification runs inline after creation (small, non-blocking work).
    media_key = media_mime = None
    if body.photo_media_id:
        from app.media.models import MediaAsset

        m = (
            await session.execute(
                select(MediaAsset).where(
                    MediaAsset.id == body.photo_media_id, MediaAsset.organization_id == ctx.org_id
                )
            )
        ).scalar_one_or_none()
        if m:
            media_key, media_mime = m.storage_key, m.mime_type
    inference = await classify_waste_report(
        session,
        organization_id=ctx.org_id,
        description=body.description,
        media_id=body.photo_media_id,
        media_storage_key=media_key,
        media_mime=media_mime,
        input_ref=report.id,
    )
    await attach_inference(session, report, inference)
    await session.commit()
    return await _report_out(session, report)


@router.post("/reports/anonymous", response_model=ReportOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(rate_limit("write"))])
async def create_anonymous_report_endpoint(
    request: Request,
    session: DbSession,
    org_slug: str = Form(...),
    description: str | None = Form(None),
    latitude: float = Form(...),
    longitude: float = Form(...),
    address: str | None = Form(None),
    contact: str | None = Form(None),
    photo: UploadFile | None = File(None),
):
    """Controlled anonymous reporting (per-org opt-in, IP rate-limited)."""
    from app.orgs.models import Organization

    org = (
        await session.execute(select(Organization).where(Organization.slug == org_slug))
    ).scalar_one_or_none()
    if org is None:
        raise NotFoundError("Organization not found.")
    if not org.allow_anonymous_reports:
        raise ValidationApiError("This organization does not accept anonymous reports.")
    from app.core.db import unscoped

    with unscoped(session):
        photo_media = None
        if photo is not None and photo.filename:
            photo_media = await store_upload(session, org.id, uploader_user_id=None, upload=photo)
        report = await create_report(
            session,
            organization_id=org.id,
            reporter_user_id=None,
            description=description,
            category_guess=None,
            latitude=latitude,
            longitude=longitude,
            location_accuracy_m=None,
            address=address,
            source="web",
            photo_media_id=photo_media.id if photo_media else None,
            is_anonymous=True,
            contact=contact,
            anon_ip=client_ip(request),
        )
        inference = await classify_waste_report(
            session,
            organization_id=org.id,
            description=description,
            media_id=photo_media.id if photo_media else None,
            media_storage_key=photo_media.storage_key if photo_media else None,
            media_mime=photo_media.mime_type if photo_media else None,
            input_ref=report.id,
        )
    await attach_inference(session, report, inference)
    await session.commit()
    return await _report_out(session, report)


@router.get("/reports")
async def list_reports_endpoint(
    ctx: AuthCtx,
    session: DbSession,
    paging=Depends(page_params),
    status_filter: str | None = None,
    severity: str | None = None,
    zone_id: uuid.UUID | None = None,
    mine: bool = False,
    near_lat: float | None = None,
    near_lng: float | None = None,
    near_radius_m: float = 1500,
    order: str = "recent",
):
    read_all = ctx.has_perm("report:read_all")
    items, total = await list_reports(
        session,
        organization_id=ctx.org_id,
        viewer_user_id=ctx.user.id,
        read_all=read_all,
        status=status_filter,
        severity=severity,
        zone_id=zone_id,
        mine_only=mine,
        near_lat=near_lat,
        near_lng=near_lng,
        near_radius_m=near_radius_m,
        limit=paging.limit,
        offset=paging.offset,
        order=order,
    )
    return {
        "items": [await _report_out(session, r) for r in items],
        "pagination": {"page": paging.page, "page_size": paging.page_size, "total": total},
    }


@router.get("/reports/{report_id}")
async def get_report_endpoint(report_id: uuid.UUID, ctx: AuthCtx, session: DbSession):
    report = await get_report(session, ctx.org_id, report_id)
    ctx.ensure_perm("report:read_all", "report:read", report.reporter_user_id)
    return await _report_out(session, report)


@router.get("/reports/{report_id}/timeline", response_model=list[ReportEventOut])
async def timeline_endpoint(report_id: uuid.UUID, ctx: AuthCtx, session: DbSession):
    report = await get_report(session, ctx.org_id, report_id)
    ctx.ensure_perm("report:read_all", "report:read", report.reporter_user_id)
    events = await report_timeline(session, ctx.org_id, report_id)
    return [ReportEventOut.model_validate(e) for e in events]


@router.patch("/reports/{report_id}/status", response_model=ReportOut)
async def update_status_endpoint(report_id: uuid.UUID, body: ReportStatusUpdate, ctx: AuthCtx, session: DbSession):
    report = await get_report(session, ctx.org_id, report_id)
    ctx.ensure_perm("report:triage", "report:read", report.reporter_user_id)
    if body.status in ("resolved", "rejected") and not ctx.has_perm("report:resolve"):
        ctx.require_perm("report:resolve")
    report = await update_status(
        session,
        organization_id=ctx.org_id,
        report_id=report_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        new_status=body.status,
        note=body.note,
        severity=body.severity,
        confirmed_category_id=body.confirmed_category_id,
        resolution_notes=body.resolution_notes,
    )
    await session.commit()
    return await _report_out(session, report)


@router.post("/reports/{report_id}/assign", response_model=ReportOut,
             dependencies=[Depends(require_perm("report:assign"))])
async def assign_endpoint(report_id: uuid.UUID, body: ReportAssign, ctx: AuthCtx, session: DbSession):
    report = await assign_report(
        session,
        organization_id=ctx.org_id,
        report_id=report_id,
        assignee_user_id=body.user_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
    )
    await session.commit()
    return await _report_out(session, report)


# --- Categories ---------------------------------------------------------------


class CategoryCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    color_hex: str = "#64748b"
    icon: str = "trash-2"
    default_handling_guidance: str | None = None


class CategoryOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    color_hex: str
    icon: str
    default_handling_guidance: str | None
    sort_order: int
    is_active: bool


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(ctx: AuthCtx, session: DbSession):
    cats = (
        await session.execute(
            select(WasteCategory)
            .where(WasteCategory.organization_id == ctx.org_id, WasteCategory.is_active.is_(True))
            .order_by(WasteCategory.sort_order)
        )
    ).scalars().all()
    return [CategoryOut(id=c.id, code=c.code, name=c.name, description=c.description,
                        color_hex=c.color_hex, icon=c.icon,
                        default_handling_guidance=c.default_handling_guidance,
                        sort_order=c.sort_order, is_active=c.is_active) for c in cats]


@router.post("/categories", response_model=CategoryOut, status_code=201,
             dependencies=[Depends(require_perm("category:manage"))])
async def create_category(body: CategoryCreate, ctx: AuthCtx, session: DbSession):
    from app.audit.service import record as audit
    from app.waste.models import WasteCategory as WC

    dupe = (
        await session.execute(
            select(WC.id).where(WC.organization_id == ctx.org_id, WC.code == body.code)
        )
    ).scalar_one_or_none()
    if dupe:
        raise ValidationApiError("Category code already exists.")
    cat = WC(
        organization_id=ctx.org_id,
        code=body.code,
        name=body.name,
        description=body.description,
        color_hex=body.color_hex,
        icon=body.icon,
        default_handling_guidance=body.default_handling_guidance,
        sort_order=500,
    )
    session.add(cat)
    await audit(
        session,
        action="category.create",
        resource_type="waste_category",
        resource_id=cat.id,
        organization_id=ctx.org_id,
        actor_user_id=ctx.user.id,
        actor_label=ctx.user.email,
        after={"code": body.code, "name": body.name},
    )
    await session.commit()
    return CategoryOut(id=cat.id, code=cat.code, name=cat.name, description=cat.description,
                       color_hex=cat.color_hex, icon=cat.icon,
                       default_handling_guidance=cat.default_handling_guidance,
                       sort_order=cat.sort_order, is_active=cat.is_active)