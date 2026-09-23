"""Collection endpoints: points, schedules, events."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.audit.service import record as audit
from app.auth.deps import AuthCtx, DbSession, require_perm
from app.collection.models import CollectionEvent, CollectionPoint, CollectionSchedule
from app.collection.service import complete_event, create_point, create_schedule, list_events
from app.core.errors import NotFoundError, ValidationApiError
from app.core.gis import MAX_LAT, MAX_LNG, MIN_LAT, MIN_LNG

router = APIRouter(prefix="/collection", tags=["collection"])


class PointIn(BaseModel):
    code: str = Field(min_length=2, max_length=48)
    name: str = Field(min_length=2, max_length=160)
    kind: str = "bin_station"
    zone_id: uuid.UUID | None = None
    latitude: float = Field(ge=MIN_LAT, le=MAX_LAT)
    longitude: float = Field(ge=MIN_LNG, le=MAX_LNG)
    address: str | None = None
    households_served: int | None = Field(default=None, ge=1, le=100_000)
    capacity_volume_m3: float | None = Field(default=None, ge=0, le=100)
    pickup_notes: str | None = None


class PointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    kind: str
    zone_id: uuid.UUID | None
    latitude: float
    longitude: float
    address: str | None
    households_served: int | None
    capacity_volume_m3: float | None
    est_fill_pct: float | None
    pickup_notes: str | None
    is_active: bool
    created_at: datetime


@router.get("/points", response_model=list[PointOut])
async def list_points(ctx: AuthCtx, session: DbSession, zone_id: uuid.UUID | None = None, limit: int = 500):
    q = select(CollectionPoint).where(
        CollectionPoint.organization_id == ctx.org_id, CollectionPoint.is_active.is_(True)
    )
    if zone_id:
        q = q.where(CollectionPoint.zone_id == zone_id)
    pts = (await session.execute(q.order_by(CollectionPoint.code).limit(min(limit, 2000)))).scalars().all()
    return [PointOut.model_validate(p) for p in pts]


@router.post("/points", response_model=PointOut, status_code=201,
             dependencies=[Depends(require_perm("collection:manage"))])
async def create_point_endpoint(body: PointIn, ctx: AuthCtx, session: DbSession):
    pt = await create_point(
        session,
        organization_id=ctx.org_id,
        **body.model_dump(),
    )
    await audit(
        session, action="collection_point.create", resource_type="collection_point",
        resource_id=pt.id, organization_id=ctx.org_id, actor_user_id=ctx.user.id,
        actor_label=ctx.user.email, after={"code": pt.code, "name": pt.name},
    )
    await session.commit()
    return PointOut.model_validate(pt)


class ScheduleIn(BaseModel):
    collection_point_id: uuid.UUID
    waste_category_id: uuid.UUID | None = None
    frequency: str = "weekly"  # daily | weekly | biweekly | monthly
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_date: date
    window_start: str | None = None  # "HH:MM"
    window_end: str | None = None


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    collection_point_id: uuid.UUID
    waste_category_id: uuid.UUID | None
    frequency: str
    weekday: int | None
    start_date: date
    is_active: bool


@router.get("/schedules", response_model=list[ScheduleOut])
async def list_schedules(ctx: AuthCtx, session: DbSession, point_id: uuid.UUID | None = None):
    q = select(CollectionSchedule).where(
        CollectionSchedule.organization_id == ctx.org_id, CollectionSchedule.is_active.is_(True)
    )
    if point_id:
        q = q.where(CollectionSchedule.collection_point_id == point_id)
    items = (await session.execute(q)).scalars().all()
    return [ScheduleOut.model_validate(s) for s in items]


@router.post("/schedules", response_model=ScheduleOut, status_code=201,
             dependencies=[Depends(require_perm("collection:manage"))])
async def create_schedule_endpoint(body: ScheduleIn, ctx: AuthCtx, session: DbSession):
    s = await create_schedule(session, organization_id=ctx.org_id, **body.model_dump())
    await session.commit()
    return ScheduleOut.model_validate(s)


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    collection_point_id: uuid.UUID
    point_name: str | None = None
    point_code: str | None = None
    waste_category_id: uuid.UUID | None
    scheduled_date: date
    status: str
    route_id: uuid.UUID | None
    vehicle_id: uuid.UUID | None
    collector_user_id: uuid.UUID | None
    completed_at: datetime | None
    weight_kg: float | None
    contamination_flag: bool
    skip_reason: str | None
    notes: str | None


@router.get("/events")
async def list_events_endpoint(
    ctx: AuthCtx,
    session: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
):
    items, total = await list_events(
        session,
        organization_id=ctx.org_id,
        date_from=date_from,
        date_to=date_to,
        status=status_filter,
        limit=min(page_size, 200),
        offset=(page - 1) * page_size,
    )
    return {"items": items, "pagination": {"page": page, "page_size": page_size, "total": total}}


class CompleteEventIn(BaseModel):
    weight_kg: float | None = Field(default=None, ge=0, le=50000)
    contamination_flag: bool = False
    skip_reason: str | None = Field(default=None, max_length=48)
    notes: str | None = Field(default=None, max_length=2000)
    status: str = "completed"  # completed | missed | skipped | partial


@router.post("/events/{event_id}/complete", response_model=EventOut,
             dependencies=[Depends(require_perm("collection:complete"))])
async def complete_event_endpoint(event_id: uuid.UUID, body: CompleteEventIn, ctx: AuthCtx, session: DbSession):
    event = await complete_event(
        session,
        organization_id=ctx.org_id,
        event_id=event_id,
        collector_user_id=ctx.user.id,
        status=body.status,
        weight_kg=body.weight_kg,
        contamination_flag=body.contamination_flag,
        skip_reason=body.skip_reason,
        notes=body.notes,
    )
    await session.commit()
    return EventOut.model_validate(event)
