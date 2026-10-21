"""Route planning use cases. Reading needs ``routes:read``; planning needs ``routes:manage``.

A plan is a *proposal*: the order of stops that minimises straight-line distance for one
vehicle (see ``optimizer``). It is stored as a draft, can be published or cancelled, and never
changes the collection tasks it orders.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Literal

from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import AppError, NotFoundError, UnprocessableError
from app.integrations.mapping.base import LatLng, RoadRouteProvider, RoadRouteUnavailable
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.collection.constants import CollectionTaskStatus
from app.modules.collection.models import CollectionTask
from app.modules.facilities import repository as facilities
from app.modules.facilities.constants import FacilityStatus
from app.modules.facilities.models import Facility
from app.modules.fleet import repository as fleet
from app.modules.fleet.constants import VehicleStatus
from app.modules.route_planning import optimizer, repository
from app.modules.route_planning.constants import RoutePlanStatus
from app.modules.route_planning.models import RoutePlan
from app.modules.route_planning.schemas import (
    PlanCreate,
    PlanDetail,
    PlanOut,
    RoadRouteOut,
    StopOut,
)
from app.modules.users import repository as users

PLANNABLE = (CollectionTaskStatus.PENDING, CollectionTaskStatus.ASSIGNED)
_KM = decimal.Decimal("0.001")

ALLOWED: dict[RoutePlanStatus, frozenset[RoutePlanStatus]] = {
    RoutePlanStatus.DRAFT: frozenset({RoutePlanStatus.PUBLISHED, RoutePlanStatus.CANCELLED}),
    RoutePlanStatus.PUBLISHED: frozenset({RoutePlanStatus.CANCELLED}),
    RoutePlanStatus.IN_PROGRESS: frozenset(),
    RoutePlanStatus.COMPLETED: frozenset(),
    RoutePlanStatus.CANCELLED: frozenset(),
}


class TaskNotPlannableError(AppError):
    status_code = 409
    code = "task_not_plannable"


class TaskAlreadyPlannedError(AppError):
    status_code = 409
    code = "task_already_planned"


class CapacityExceededError(AppError):
    status_code = 409
    code = "capacity_exceeded"


class VehicleNotUsableError(AppError):
    status_code = 409
    code = "vehicle_unavailable"


class InvalidPlanTransitionError(AppError):
    status_code = 409
    code = "invalid_plan_transition"


def _km(metres: float) -> decimal.Decimal:
    return (decimal.Decimal(repr(metres)) / 1000).quantize(_KM, rounding=decimal.ROUND_HALF_UP)


def _coord(lat: decimal.Decimal | None, lon: decimal.Decimal | None) -> tuple[float, float]:
    if lat is None or lon is None:  # validated earlier; kept as a guard, never silently zero
        raise UnprocessableError("A route point has no coordinates")
    return float(lat), float(lon)


def _facility_point(db: Session, facility_id: uuid.UUID | None, role: str) -> Facility | None:
    if facility_id is None:
        return None
    facility = facilities.get(db, facility_id)
    if facility is None:
        raise UnprocessableError(f"{role} does not refer to an existing facility")
    if facility.status is not FacilityStatus.ACTIVE:
        raise UnprocessableError(f"{role} must be an active facility")
    if facility.latitude is None or facility.longitude is None:
        raise UnprocessableError(f"{role} has no coordinates, so a route cannot be computed")
    return facility


def create_plan(
    db: Session, principal: Principal, payload: PlanCreate, *, context: RequestContext
) -> PlanDetail:
    if payload.planned_date < dt.datetime.now(dt.UTC).date():
        raise UnprocessableError("planned_date cannot be in the past")
    if len(set(payload.task_ids)) != len(payload.task_ids):
        raise UnprocessableError("task_ids must be unique")
    start = _facility_point(db, payload.start_facility_id, "start_facility_id")
    end = _facility_point(db, payload.end_facility_id, "end_facility_id")
    if start is None:  # the schema makes start_facility_id mandatory
        raise UnprocessableError("start_facility_id is required")

    found = {t.id: (t, est) for t, est in repository.tasks_with_estimates(db, payload.task_ids)}
    missing = [str(i) for i in payload.task_ids if i not in found]
    if missing:
        raise UnprocessableError("Unknown task ids: " + ", ".join(missing))

    def _named(ids: list[uuid.UUID]) -> str:
        return ", ".join(f"“{found[i][0].title}”" for i in ids)

    def _task_details(ids: list[uuid.UUID]) -> list[dict[str, str]]:
        return [{"task_id": str(i), "title": found[i][0].title} for i in ids]

    wrong_status = [t.id for t, _ in found.values() if t.status not in PLANNABLE]
    if wrong_status:
        raise TaskNotPlannableError(
            "Only pending or assigned tasks can be planned. Not plannable: " + _named(wrong_status),
            details=_task_details(wrong_status),
        )
    no_coords = [t.id for t, _ in found.values() if t.latitude is None or t.longitude is None]
    if no_coords:
        raise UnprocessableError(
            "Tasks without coordinates cannot be routed: " + _named(no_coords),
            details=_task_details(no_coords),
        )
    planned = repository.tasks_in_active_plans(db, payload.task_ids)
    if planned:
        ids = sorted(planned, key=str)
        raise TaskAlreadyPlannedError(
            "Already in an active route plan: "
            + ", ".join(f"“{found[i][0].title}” (plan “{planned[i]}”)" for i in ids),
            details=[
                {"task_id": str(i), "title": found[i][0].title, "plan_name": planned[i]}
                for i in ids
            ],
        )

    warnings: list[str] = []
    vehicle_id = payload.vehicle_id
    if vehicle_id is not None:
        vehicle = fleet.get(db, vehicle_id)
        if vehicle is None:
            raise UnprocessableError("vehicle_id does not refer to an existing vehicle")
        if vehicle.status not in (VehicleStatus.AVAILABLE, VehicleStatus.IN_SERVICE):
            raise VehicleNotUsableError(f"A {vehicle.status.value} vehicle cannot be planned")
        known = [est for _, est in found.values() if est is not None]
        total = sum(known, decimal.Decimal(0))
        if total > vehicle.capacity_kg:
            raise CapacityExceededError(
                f"Estimated weight {total} kg exceeds the vehicle capacity {vehicle.capacity_kg} kg"
            )
        unknown = len(found) - len(known)
        if unknown:
            warnings.append(
                f"{unknown} of {len(found)} tasks have no weight estimate; vehicle capacity "
                "could only be checked against the others."
            )
    else:
        warnings.append("No vehicle selected: capacity was not checked.")
    if payload.driver_id is not None:
        driver = users.get_by_id(db, payload.driver_id)
        if driver is None or not driver.is_active:
            raise UnprocessableError("driver_id must be an active user")
        if "collection:execute" not in users.permission_codes(db, driver.id):
            raise UnprocessableError("driver_id must be a user who can execute collection tasks")

    ordered_tasks = [found[i][0] for i in payload.task_ids]
    points = [_coord(start.latitude, start.longitude)]
    points += [_coord(t.latitude, t.longitude) for t in ordered_tasks]
    final_index: int | None = None
    if end is not None:
        points.append(_coord(end.latitude, end.longitude))
        final_index = len(points) - 1
    dist = optimizer.haversine_matrix(points)
    result = optimizer.optimize(
        dist, depot=0, stops=list(range(1, len(ordered_tasks) + 1)), final=final_index
    )

    plan = repository.add_plan(
        db,
        name=payload.name,
        planned_date=payload.planned_date,
        status=RoutePlanStatus.DRAFT,
        vehicle_id=vehicle_id,
        driver_id=payload.driver_id,
        start_facility_id=start.id,
        end_facility_id=end.id if end is not None else None,
        created_by_id=principal.user_id,
        total_distance_km=_km(result.length),
        estimated_duration_min=None,
        optimizer=f"{optimizer.OPTIMIZER_NAME} {optimizer.OPTIMIZER_VERSION} ({result.method})",
    )
    sequence = 0
    for index in result.order:
        sequence += 1
        repository.add_stop(
            db,
            route_plan_id=plan.id,
            sequence=sequence,
            collection_task_id=ordered_tasks[index - 1].id,
        )
    if end is not None:
        repository.add_stop(db, route_plan_id=plan.id, sequence=sequence + 1, facility_id=end.id)
    audit.record(
        db,
        action="route_plan.created",
        entity_type="route_plan",
        entity_id=plan.id,
        actor_id=principal.user_id,
        context=context,
        changes={
            "tasks": len(ordered_tasks),
            "total_distance_km": str(plan.total_distance_km),
            "optimizer": plan.optimizer,
        },
    )
    db.commit()
    return _detail(db, plan, warnings)


def _detail(db: Session, plan: RoutePlan, warnings: list[str] | None = None) -> PlanDetail:
    start = facilities.get(db, plan.start_facility_id) if plan.start_facility_id else None
    rows = repository.stops(db, plan.id)
    task_ids = [r.collection_task_id for r in rows if r.collection_task_id is not None]
    tasks: dict[uuid.UUID, CollectionTask] = (
        {t.id: t for t, _ in repository.tasks_with_estimates(db, task_ids)} if task_ids else {}
    )
    origin = _coord(start.latitude, start.longitude) if start is not None else None
    here = origin
    stops: list[StopOut] = []
    for row in rows:
        kind: Literal["task", "facility"]
        if row.collection_task_id is not None:
            task = tasks[row.collection_task_id]
            lat, lon, label, kind = task.latitude, task.longitude, task.title, "task"
        else:
            facility = facilities.get(db, row.facility_id) if row.facility_id else None
            if facility is None:
                raise NotFoundError("Route stop refers to a missing facility")
            lat, lon, label, kind = facility.latitude, facility.longitude, facility.name, "facility"
        point = _coord(lat, lon)
        leg = optimizer.haversine_m(*here, *point) if here is not None else 0.0
        stops.append(
            StopOut(
                sequence=row.sequence,
                kind=kind,
                collection_task_id=row.collection_task_id,
                facility_id=row.facility_id,
                label=label,
                latitude=decimal.Decimal(str(lat)),
                longitude=decimal.Decimal(str(lon)),
                leg_distance_km=_km(leg),
            )
        )
        here = point
    back = (
        optimizer.haversine_m(*here, *origin) if here is not None and origin is not None else None
    )
    base = PlanOut.model_validate(plan, from_attributes=True)
    return PlanDetail(
        **base.model_dump(),
        start_label=start.name if start else None,
        start_latitude=decimal.Decimal(str(origin[0])) if origin else None,
        start_longitude=decimal.Decimal(str(origin[1])) if origin else None,
        return_leg_distance_km=_km(back) if back is not None else None,
        stops=stops,
        warnings=warnings or [],
    )


def get_plan(db: Session, plan_id: uuid.UUID) -> PlanDetail:
    plan = repository.get(db, plan_id)
    if plan is None:
        raise NotFoundError("Route plan not found")
    return _detail(db, plan)


def list_plans(
    db: Session,
    params: PageParams,
    *,
    status: RoutePlanStatus | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    sort_by: str,
    order: SortOrder,
) -> Page[PlanOut]:
    rows, total = repository.list_page(
        db,
        params,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order=order,
    )
    return Page.build(
        [PlanOut.model_validate(r, from_attributes=True) for r in rows], total, params
    )


def transition(
    db: Session,
    principal: Principal,
    plan_id: uuid.UUID,
    target: RoutePlanStatus,
    reason: str | None,
    *,
    context: RequestContext,
) -> PlanDetail:
    plan = repository.get(db, plan_id, for_update=True)
    if plan is None:
        raise NotFoundError("Route plan not found")
    if target not in ALLOWED[plan.status]:
        db.rollback()
        raise InvalidPlanTransitionError(f"A {plan.status.value} plan cannot become {target.value}")
    before = plan.status
    plan.status = target
    audit.record(
        db,
        action=f"route_plan.{target.value}",
        entity_type="route_plan",
        entity_id=plan.id,
        actor_id=principal.user_id,
        context=context,
        changes={"from": before.value, "to": target.value, "reason": reason},
    )
    db.commit()
    db.refresh(plan)
    return _detail(db, plan)


def road_route(db: Session, plan_id: uuid.UUID, provider: RoadRouteProvider) -> RoadRouteOut:
    """Ask the routing provider for the road route through the plan, depot to depot.

    Never raises for provider problems: the answer says why no road route is available, so the
    screen can show a labelled fallback. Nothing is stored.
    """
    detail = get_plan(db, plan_id)
    if detail.start_latitude is None or detail.start_longitude is None:
        return RoadRouteOut(plan_id=plan_id, available=False, reason="too_few_points")
    depot = LatLng(float(detail.start_latitude), float(detail.start_longitude))
    points = [depot, *(LatLng(float(s.latitude), float(s.longitude)) for s in detail.stops), depot]
    outcome = provider.route(points)
    if isinstance(outcome, RoadRouteUnavailable):
        return RoadRouteOut(
            plan_id=plan_id,
            available=False,
            provider=outcome.provider,
            reason=outcome.reason,
            detail=outcome.detail,
        )
    return RoadRouteOut(
        plan_id=plan_id,
        available=True,
        provider=outcome.provider,
        encoded_polylines=list(outcome.encoded_polylines),
        distance_m=outcome.distance_m,
        duration_s=outcome.duration_s,
        traffic_aware=outcome.traffic_aware,
        request_count=outcome.request_count,
    )
