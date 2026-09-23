"""Routing endpoints: generation, listing, field execution."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.auth.deps import AuthCtx, DbSession, require_perm
from app.collection.models import CollectionPoint
from app.core.errors import NotFoundError, ValidationApiError
from app.routing.models import Route, RouteStop
from app.routing.service import (
    generate_route,
    get_route,
    my_routes,
    route_with_stops,
    set_route_status,
    update_stop,
)

router = APIRouter(prefix="/routes", tags=["routing"])


class GenerateRouteIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    service_date: date
    depot_lat: float
    depot_lng: float
    zone_id: uuid.UUID | None = None
    point_ids: list[uuid.UUID] | None = None
    vehicle_ids: list[uuid.UUID] | None = None
    driver_user_id: uuid.UUID | None = None
    use_fill_levels: bool = True


class StopOut(BaseModel):
    id: uuid.UUID
    sequence_no: int
    collection_point_id: uuid.UUID
    point_name: str | None = None
    point_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    planned_arrival_offset_min: float | None
    est_distance_from_prev_km: float | None
    priority: int
    status: str
    completed_at: datetime | None
    weight_kg: float | None
    skip_reason: str | None
    contamination_flag: bool
    notes: str | None


class RouteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    service_date: date
    status: str
    zone_id: uuid.UUID | None
    vehicle_id: uuid.UUID | None
    driver_user_id: uuid.UUID | None
    depot_lat: float
    depot_lng: float
    total_distance_km: float | None
    total_duration_min: float | None
    planned_weight_kg: float | None
    stops_count: int
    optimization: dict
    geometry: dict | None
    geometry_is_estimated: bool
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class RouteDetail(RouteOut):
    stops: list[StopOut] = []
    completed_stops: int = 0


def _route_out(r: Route) -> dict:
    out = RouteOut.model_validate(r).model_dump()
    out["total_distance_km"] = float(r.total_distance_km) if r.total_distance_km is not None else None
    out["total_duration_min"] = float(r.total_duration_min) if r.total_duration_min is not None else None
    out["planned_weight_kg"] = float(r.planned_weight_kg) if r.planned_weight_kg is not None else None
    return out


@router.post("/generate", response_model=RouteDetail, status_code=201,
             dependencies=[Depends(require_perm("route:generate"))])
async def generate_route_endpoint(body: GenerateRouteIn, ctx: AuthCtx, session: DbSession):
    route = await generate_route(
        session,
        organization_id=ctx.org_id,
        name=body.name,
        service_date=body.service_date,
        depot_lat=body.depot_lat,
        depot_lng=body.depot_lng,
        zone_id=body.zone_id,
        point_ids=body.point_ids,
        vehicle_ids=body.vehicle_ids,
        driver_user_id=body.driver_user_id,
        created_by=ctx.user.id,
        use_fill_levels=body.use_fill_levels,
    )
    await session.commit()
    return await _detail(session, ctx.org_id, route.id)


async def _detail(session, org_id: uuid.UUID, route_id: uuid.UUID) -> RouteDetail:
    route, stops, points = await route_with_stops(session, org_id, route_id)
    stop_outs = []
    for s in stops:
        p = points.get(s.collection_point_id)
        stop_outs.append(
            StopOut(
                id=s.id,
                sequence_no=s.sequence_no,
                collection_point_id=s.collection_point_id,
                point_name=p.name if p else None,
                point_code=p.code if p else None,
                latitude=p.latitude if p else None,
                longitude=p.longitude if p else None,
                address=p.address if p else None,
                planned_arrival_offset_min=s.planned_arrival_offset_min,
                est_distance_from_prev_km=s.est_distance_from_prev_km,
                priority=s.priority,
                status=s.status.value,
                completed_at=s.completed_at,
                weight_kg=s.weight_kg,
                skip_reason=s.skip_reason,
                contamination_flag=s.contamination_flag,
                notes=s.notes,
            )
        )
    base = _route_out(route)
    return RouteDetail(
        **base,
        stops=stop_outs,
        completed_stops=sum(1 for s in stops if s.status.value in ("completed", "skipped")),
    )


@router.get("", response_model=list[dict])
async def list_routes(ctx: AuthCtx, session: DbSession, day: date | None = None, limit: int = 50):
    q = select(Route).where(Route.organization_id == ctx.org_id)
    if day:
        q = q.where(Route.service_date == day)
    routes = (await session.execute(q.order_by(Route.created_at.desc()).limit(min(limit, 200)))).scalars().all()
    return [_route_out(r) for r in routes]


@router.get("/my/today")
async def my_routes_today(ctx: AuthCtx, session: DbSession):
    routes = await my_routes(session, ctx.org_id, ctx.user.id, date.today())
    out = []
    for r in routes:
        d = _route_out(r)
        stops_done = (
            await session.execute(
                select(func.count()).select_from(RouteStop).where(
                    RouteStop.route_id == r.id,
                    RouteStop.status.in_(["completed", "skipped"]),
                )
            )
        ).scalar_one()
        d["completed_stops"] = stops_done
        out.append(d)
    return {"items": out}


@router.get("/{route_id}", response_model=RouteDetail)
async def get_route_endpoint(route_id: uuid.UUID, ctx: AuthCtx, session: DbSession):
    await get_route(session, ctx.org_id, route_id)
    return await _detail(session, ctx.org_id, route_id)


class RouteStatusIn(BaseModel):
    status: str  # draft | approved | in_progress | completed | cancelled


@router.patch("/{route_id}/status", response_model=dict)
async def set_status_endpoint(route_id: uuid.UUID, body: RouteStatusIn, ctx: AuthCtx, session: DbSession):
    if body.status in ("approved", "in_progress") and not ctx.has_perm("route:assign"):
        ctx.require_perm("route:assign")
    await set_route_status(session, organization_id=ctx.org_id, route_id=route_id,
                           status=body.status, actor_user_id=ctx.user.id)
    await session.commit()
    return {"ok": True}


class StopUpdateIn(BaseModel):
    status: str | None = None  # completed | skipped | failed | pending
    weight_kg: float | None = Field(default=None, ge=0, le=50000)
    skip_reason: str | None = Field(default=None, max_length=200)
    contamination_flag: bool = False
    notes: str | None = Field(default=None, max_length=2000)


@router.patch("/stops/{stop_id}", response_model=StopOut)
async def update_stop_endpoint(stop_id: uuid.UUID, body: StopUpdateIn, ctx: AuthCtx, session: DbSession):
    ctx.require_perm("route:execute")
    stop = await update_stop(
        session,
        organization_id=ctx.org_id,
        stop_id=stop_id,
        actor_user_id=ctx.user.id,
        status=body.status,
        weight_kg=body.weight_kg,
        skip_reason=body.skip_reason,
        contamination_flag=body.contamination_flag,
        notes=body.notes,
    )
    await session.commit()
    p = (
        await session.execute(
            select(CollectionPoint).where(CollectionPoint.id == stop.collection_point_id)
        )
    ).scalar_one_or_none()
    return StopOut(
        id=stop.id,
        sequence_no=stop.sequence_no,
        collection_point_id=stop.collection_point_id,
        point_name=p.name if p else None,
        point_code=p.code if p else None,
        latitude=p.latitude if p else None,
        longitude=p.longitude if p else None,
        address=p.address if p else None,
        planned_arrival_offset_min=stop.planned_arrival_offset_min,
        est_distance_from_prev_km=stop.est_distance_from_prev_km,
        priority=stop.priority,
        status=stop.status.value,
        completed_at=stop.completed_at,
        weight_kg=stop.weight_kg,
        skip_reason=stop.skip_reason,
        contamination_flag=stop.contamination_flag,
        notes=stop.notes,
    )
