"""Route generation and field execution service."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import func, select

from app.audit.service import record as audit
from app.collection.models import CollectionEvent, CollectionPoint, EventStatus
from app.core.db import AsyncSession, utcnow
from app.core.errors import NotFoundError, ValidationApiError
from app.core.logging import get_logger
from app.fleet.models import Vehicle
from app.notifications.service import notify_user
from app.routing.models import Route, RouteStatus, RouteStop, StopStatus
from app.routing.optimizer import OptimisationResult, StopSpec, VehicleSpec, solve
from app.routing.roads import route_path

log = get_logger("routing")

FILL_DEMAND_BASE_KG = 120.0  # assumed payload for a fully-full standard bin


async def generate_route(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    name: str,
    service_date: date,
    depot_lat: float,
    depot_lng: float,
    zone_id: uuid.UUID | None = None,
    point_ids: list[uuid.UUID] | None = None,
    vehicle_ids: list[uuid.UUID] | None = None,
    driver_user_id: uuid.UUID | None = None,
    created_by: uuid.UUID | None = None,
    use_fill_levels: bool = True,
) -> Route:
    """Gather stops, optimise sequencing (OR-Tools), attach road geometry, persist."""
    q = select(CollectionPoint).where(
        CollectionPoint.organization_id == organization_id, CollectionPoint.is_active.is_(True)
    )
    if zone_id:
        q = q.where(CollectionPoint.zone_id == zone_id)
    if point_ids:
        q = q.where(CollectionPoint.id.in_(point_ids))
    points = (await session.execute(q)).scalars().all()
    if not points:
        raise ValidationApiError("No collection points match this request.")

    vq = select(Vehicle).where(
        Vehicle.organization_id == organization_id, Vehicle.status == "active"
    )
    if vehicle_ids:
        vq = vq.where(Vehicle.id.in_(vehicle_ids))
    vehicles = (await session.execute(vq)).scalars().all()
    if not vehicles:
        raise ValidationApiError("No active vehicles available.")

    # Devices enrich demand: fill percentage -> expected payload.
    fill_by_point = {}
    from app.iot.models import Device

    devices = (
        await session.execute(
            select(Device).where(Device.organization_id == organization_id)
        )
    ).scalars().all()
    for d in devices:
        if d.collection_point_id and d.current_fill_pct is not None:
            fill_by_point[d.collection_point_id] = d.current_fill_pct

    stops: list[StopSpec] = []
    for p in points:
        fill = fill_by_point.get(p.id)
        if use_fill_levels and fill is not None:
            demand = FILL_DEMAND_BASE_KG * max(0.05, fill / 100.0)
        elif p.est_fill_pct is not None:
            demand = FILL_DEMAND_BASE_KG * max(0.05, p.est_fill_pct / 100.0)
        else:
            demand = FILL_DEMAND_BASE_KG * 0.5
        stops.append(
            StopSpec(
                key=str(p.id),
                lat=p.latitude,
                lng=p.longitude,
                demand_kg=demand,
                service_min=4.0 if p.kind == "bin_station" else 6.0,
                priority=1 if (fill is not None and fill >= 85) else 0,
            )
        )

    vehicle_specs = [
        VehicleSpec(key=str(v.id), capacity_kg=float(v.capacity_kg or 5000)) for v in vehicles
    ]
    result: OptimisationResult = solve(
        depot=(depot_lat, depot_lng), stops=stops, vehicles=vehicle_specs
    )

    vehicle_map = {str(v.id): v for v in vehicles}
    point_map = {str(p.id): p for p in points}

    # Use the plan with stops for the primary route; multi-vehicle support
    # creates one route per vehicle plan that has stops.
    code_seq = (await session.execute(
        select(func.count()).select_from(Route).where(Route.organization_id == organization_id)
    )).scalar_one()

    primary_plan = next((p for p in result.plans if p.stop_keys), None)
    if primary_plan is None:
        raise ValidationApiError(
            "The optimiser could not assign any stops to vehicles. "
            "Check vehicle capacities and stop demand."
        )

    geometry_estimated = True

    created_routes: list[Route] = []
    for plan_i, plan in enumerate(result.plans):
        if not plan.stop_keys:
            continue
        v = vehicle_map[plan.vehicle_key]
        waypoint_points = [(depot_lat, depot_lng)] + [
            (point_map[k].latitude, point_map[k].longitude) for k in plan.stop_keys
        ] + [(depot_lat, depot_lng)]
        road = await route_path(waypoint_points)
        geometry_estimated = road.estimated

        route = Route(
            organization_id=organization_id,
            code=f"RT-{service_date.strftime('%y%m%d')}-{code_seq + plan_i + 1:03d}",
            name=name if len(result.plans) == 1 else f"{name} — vehicle {v.code}",
            service_date=service_date,
            status=RouteStatus.draft,
            zone_id=zone_id,
            vehicle_id=v.id,
            driver_user_id=driver_user_id,
            depot_lat=depot_lat,
            depot_lng=depot_lng,
            total_distance_km=road.distance_km if not road.estimated else plan.distance_km * 1.3,
            total_duration_min=road.duration_min if not road.estimated else plan.duration_min,
            planned_weight_kg=plan.load_kg,
            stops_count=len(plan.stop_keys),
            optimization={
                "solver": result.solver,
                "solver_status": result.solver_status,
                "solve_ms": result.solve_ms,
                "geometry_provider": road.provider,
                "geometry_estimated": road.estimated,
                "road_distance_factor": settings_factor(),
                "unassigned_stops": result.unassigned,
                "vehicles_used": len([p for p in result.plans if p.stop_keys]),
            },
            geometry={"type": "LineString", "coordinates": road.geometry},
            geometry_is_estimated=road.estimated,
            created_by=created_by,
        )
        session.add(route)
        await session.flush()

        cumulative_distance = 0.0
        cumulative_time = 0.0
        for seq, key in enumerate(plan.stop_keys, start=1):
            p = point_map[key]
            if seq > 1:
                prev = point_map[plan.stop_keys[seq - 2]]
                cumulative_distance += _km(prev, p)
                cumulative_time += _km(prev, p) / 22.0 * 60
            session.add(
                RouteStop(
                    organization_id=organization_id,
                    route_id=route.id,
                    sequence_no=seq,
                    collection_point_id=p.id,
                    planned_arrival_offset_min=cumulative_time,
                    est_distance_from_prev_km=0 if seq == 1 else _km(prev, p),
                    est_duration_from_prev_min=0 if seq == 1 else _km(prev, p) / 22.0 * 60,
                    priority=1 if (fill_by_point.get(p.id, 0) or 0) >= 85 else 0,
                    status=StopStatus.pending,
                    created_at=utcnow(),
                )
            )
            # Link today's collection events to this route for execution.
            event = (
                await session.execute(
                    select(CollectionEvent).where(
                        CollectionEvent.organization_id == organization_id,
                        CollectionEvent.collection_point_id == p.id,
                        CollectionEvent.scheduled_date == service_date,
                    )
                )
            ).scalar_one_or_none()
            if event is not None:
                event.route_id = route.id
        created_routes.append(route)

    await audit(
        session,
        action="route.generate",
        resource_type="route",
        resource_id=created_routes[0].id,
        organization_id=organization_id,
        actor_user_id=created_by,
        after={
            "solver": result.solver,
            "status": result.solver_status,
            "stops": sum(r.stops_count for r in created_routes),
            "unassigned": len(result.unassigned),
            "geometry_estimated": geometry_estimated,
        },
    )
    return created_routes[0]


def settings_factor() -> float:
    from app.core.config import settings

    return settings.road_distance_factor


def _km(a, b) -> float:
    from app.core.gis import haversine_km

    return round(haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) * 1.3, 3)


async def get_route(session, organization_id: uuid.UUID, route_id: uuid.UUID) -> Route:
    r = (
        await session.execute(
            select(Route).where(Route.id == route_id, Route.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if r is None:
        raise NotFoundError("Route not found.")
    return r


async def route_with_stops(session, organization_id: uuid.UUID, route_id: uuid.UUID):
    route = await get_route(session, organization_id, route_id)
    stops = (
        await session.execute(
            select(RouteStop)
            .where(RouteStop.route_id == route_id)
            .order_by(RouteStop.sequence_no)
        )
    ).scalars().all()
    point_ids = [s.collection_point_id for s in stops]
    points = {}
    if point_ids:
        pts = (
            await session.execute(select(CollectionPoint).where(CollectionPoint.id.in_(point_ids)))
        ).scalars().all()
        points = {p.id: p for p in pts}
    return route, stops, points


async def set_route_status(
    session, *, organization_id: uuid.UUID, route_id: uuid.UUID, status: str, actor_user_id
) -> Route:
    route = await get_route(session, organization_id, route_id)
    try:
        target = RouteStatus(status)
    except ValueError as e:
        raise ValidationApiError(f"Unknown route status '{status}'.") from e
    if target == RouteStatus.in_progress:
        route.started_at = utcnow()
        if route.vehicle_id:
            v = (
                await session.execute(
                    select(Vehicle).where(Vehicle.id == route.vehicle_id)
                )
            ).scalar_one_or_none()
            if v:
                v.current_route_id = route.id
    if target == RouteStatus.completed:
        route.completed_at = utcnow()
        if route.vehicle_id:
            v = (
                await session.execute(
                    select(Vehicle).where(Vehicle.id == route.vehicle_id)
                )
            ).scalar_one_or_none()
            if v and v.current_route_id == route.id:
                v.current_route_id = None
    route.status = target
    if route.driver_user_id:
        await notify_user(
            session,
            user_id=route.driver_user_id,
            organization_id=organization_id,
            category="route_assignment",
            title=f"Route {route.code} is {target.value.replace('_', ' ')}",
            body=route.name,
            data={"route_id": str(route.id), "status": target.value},
        )
    await audit(
        session,
        action="route.status",
        resource_type="route",
        resource_id=route.id,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        after={"status": target.value},
    )
    return route


async def update_stop(
    session, *, organization_id: uuid.UUID, stop_id: uuid.UUID, actor_user_id: uuid.UUID,
    status: str | None = None, weight_kg: float | None = None, skip_reason: str | None = None,
    contamination_flag: bool = False, notes: str | None = None,
):
    stop = (
        await session.execute(
            select(RouteStop).where(
                RouteStop.id == stop_id, RouteStop.organization_id == organization_id
            )
        )
    ).scalar_one_or_none()
    if stop is None:
        raise NotFoundError("Route stop not found.")
    if status:
        try:
            stop.status = StopStatus(status)
        except ValueError as e:
            raise ValidationApiError(f"Unknown stop status '{status}'.") from e
        if status in ("completed", "skipped", "failed"):
            stop.completed_at = utcnow()
            # Keep today's collection event in sync with field execution.
            route = await get_route(session, organization_id, stop.route_id)
            event = (
                await session.execute(
                    select(CollectionEvent).where(
                        CollectionEvent.organization_id == organization_id,
                        CollectionEvent.collection_point_id == stop.collection_point_id,
                        CollectionEvent.scheduled_date == route.service_date,
                    )
                )
            ).scalar_one_or_none()
            if event is not None and event.status == EventStatus.scheduled:
                event.status = (
                    EventStatus.completed if status == "completed"
                    else EventStatus.skipped
                )
                event.route_id = route.id
                event.collector_user_id = actor_user_id
                if status == "completed":
                    event.completed_at = utcnow()
                    event.weight_kg = weight_kg
                    event.contamination_flag = contamination_flag
                    if weight_kg and weight_kg > 0:
                        from app.sustainability.models import DataQuality, WasteTreatment

                        destination = "landfill"
                        if event.waste_category_id:
                            from app.collection.service import _default_destination

                            destination = await _default_destination(
                                session, organization_id, event.waste_category_id
                            )
                        session.add(
                            WasteTreatment(
                                organization_id=organization_id,
                                treatment_date=route.service_date,
                                waste_category_id=event.waste_category_id,
                                destination=destination,
                                weight_kg=weight_kg,
                                quality=DataQuality.measured,
                                source_event_id=event.id,
                            )
                        )
    if weight_kg is not None:
        stop.weight_kg = weight_kg
    if skip_reason is not None:
        stop.skip_reason = skip_reason
    stop.contamination_flag = contamination_flag
    if notes is not None:
        stop.notes = notes
    return stop


async def my_routes(session, organization_id: uuid.UUID, driver_user_id: uuid.UUID, day: date):
    routes = (
        await session.execute(
            select(Route).where(
                Route.organization_id == organization_id,
                Route.driver_user_id == driver_user_id,
                Route.service_date == day,
            ).order_by(Route.created_at.desc())
        )
    ).scalars().all()
    return routes
