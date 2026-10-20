"""Vehicle tracking use cases.

Authorisation
    * ``fleet:track``     post positions, only for a vehicle the caller is currently assigned to
                          (an open collection task of theirs uses that vehicle); sources
                          ``gps_device`` and ``mobile_client``
    * ``fleet:manage``    import a past track (source ``imported``); always shown as historical
    * ``fleet:simulate``  write simulator events (source ``simulator``), and only while the
                          simulator is enabled; reset removes simulator rows only
    * ``fleet:read``      read positions. Without ``fleet:manage`` a caller sees only the vehicles
                          they are currently assigned to.

Presentation rules (derived at read time from the source and the timestamp, never stored):
real sources are LIVE within ``tracking_live_within_seconds``, DELAYED until
``tracking_stale_after_seconds`` and STALE after that; imported events are HISTORICAL; simulator
events are SIMULATED; a vehicle without any event is UNAVAILABLE. Simulator events are kept in a
separate group so they can never become a vehicle's "real" latest position.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.config import Settings
from app.core.exceptions import (
    AppError,
    ForbiddenError,
    NotFoundError,
    TooManyRequestsError,
    UnprocessableError,
)
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.collection import repository as collection
from app.modules.collection.constants import CollectionTaskStatus
from app.modules.fleet import repository as fleet
from app.modules.fleet.constants import VehicleStatus
from app.modules.fleet.models import FleetVehicle
from app.modules.route_planning import repository as plans
from app.modules.route_planning import service as plan_service
from app.modules.tracking import repository
from app.modules.tracking.constants import (
    LocationQuality,
    LocationSource,
    TrackingStatus,
)
from app.modules.tracking.models import VehicleLocationEvent
from app.modules.tracking.schemas import (
    CollectionTracking,
    IngestResult,
    LatestPositions,
    LocationOut,
    LocationReport,
    PathPoint,
    PositionOut,
    RouteTracking,
    SimulatedLocation,
    StopProgress,
    TrackingConfig,
    VehiclePosition,
)

PATH_LIMIT = 1000
MANAGE = "fleet:manage"


class VehicleRetiredError(AppError):
    status_code = 409
    code = "vehicle_retired"


class NotAssignedToVehicleError(ForbiddenError):
    code = "not_assigned_to_vehicle"


class SimulatorDisabledError(NotFoundError):
    code = "simulator_disabled"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _utc(value: dt.datetime) -> dt.datetime:
    return value.astimezone(dt.UTC)


def classify(
    source: LocationSource | None,
    recorded_at: dt.datetime | None,
    *,
    now: dt.datetime,
    settings: Settings,
) -> TrackingStatus:
    if source is None or recorded_at is None:
        return TrackingStatus.UNAVAILABLE
    if source is LocationSource.SIMULATOR:
        return TrackingStatus.SIMULATED
    if source is LocationSource.IMPORTED:
        return TrackingStatus.HISTORICAL
    age = max(0.0, (now - recorded_at).total_seconds())
    if age <= settings.tracking_live_within_seconds:
        return TrackingStatus.LIVE
    if age <= settings.tracking_stale_after_seconds:
        return TrackingStatus.DELAYED
    return TrackingStatus.STALE


def _position(event: VehicleLocationEvent, now: dt.datetime) -> PositionOut:
    return PositionOut(
        latitude=event.latitude,
        longitude=event.longitude,
        recorded_at=event.recorded_at,
        received_at=event.received_at,
        source=event.source,
        accuracy_m=event.accuracy_m,
        speed_kph=event.speed_kph,
        heading_deg=event.heading_deg,
        age_seconds=int(max(0.0, (now - event.recorded_at).total_seconds())),
        collection_task_id=event.collection_task_id,
        route_plan_id=event.route_plan_id,
    )


def _vehicle_rows(
    vehicles: Iterable[FleetVehicle],
    events: list[VehicleLocationEvent],
    *,
    now: dt.datetime,
    settings: Settings,
) -> list[VehiclePosition]:
    by_key = {(e.vehicle_id, e.source is LocationSource.SIMULATOR): e for e in events}
    rows: list[VehiclePosition] = []
    for vehicle in vehicles:
        # The real row always exists (UNAVAILABLE without an event), so simulated data can never
        # stand in for a missing real position; the simulated row is added next to it.
        for is_sim in (False, True):
            event = by_key.get((vehicle.id, is_sim))
            if event is None and is_sim:
                continue
            rows.append(
                VehiclePosition(
                    vehicle_id=vehicle.id,
                    registration_number=vehicle.registration_number,
                    vehicle_type=vehicle.vehicle_type,
                    vehicle_status=vehicle.status,
                    simulated=is_sim,
                    status=classify(
                        event.source if event else None,
                        event.recorded_at if event else None,
                        now=now,
                        settings=settings,
                    ),
                    position=_position(event, now) if event else None,
                )
            )
    return rows


def _visible_vehicle_ids(db: Session, principal: Principal) -> list[uuid.UUID] | None:
    """``None`` means every vehicle."""
    if principal.has(MANAGE):
        return None
    return repository.assigned_vehicle_ids(db, principal.user_id)


def _require_visible(db: Session, principal: Principal, vehicle_id: uuid.UUID) -> FleetVehicle:
    vehicle = fleet.get(db, vehicle_id)
    if vehicle is None:
        raise NotFoundError("Vehicle not found")
    visible = _visible_vehicle_ids(db, principal)
    if visible is not None and vehicle_id not in visible:
        # Same answer as for a vehicle that does not exist: no confirmation either way.
        raise NotFoundError("Vehicle not found")
    return vehicle


def tracking_config(settings: Settings) -> TrackingConfig:
    return TrackingConfig(
        live_within_seconds=settings.tracking_live_within_seconds,
        stale_after_seconds=settings.tracking_stale_after_seconds,
        retention_days=settings.tracking_retention_days,
        simulator_enabled=settings.simulator_enabled,
        max_events_per_minute=settings.tracking_max_events_per_minute,
        road_routing_configured=settings.google_maps_server_api_key is not None,
    )


def latest_positions(
    db: Session, principal: Principal, settings: Settings, *, include_simulated: bool
) -> LatestPositions:
    now = _now()
    visible = _visible_vehicle_ids(db, principal)
    vehicles = repository.trackable_vehicles(db, visible)
    events = repository.latest_per_vehicle(
        db, [v.id for v in vehicles], include_simulated=include_simulated
    )
    return LatestPositions(
        generated_at=now,
        live_within_seconds=settings.tracking_live_within_seconds,
        stale_after_seconds=settings.tracking_stale_after_seconds,
        items=_vehicle_rows(vehicles, events, now=now, settings=settings),
    )


def vehicle_position(
    db: Session, principal: Principal, settings: Settings, vehicle_id: uuid.UUID
) -> list[VehiclePosition]:
    vehicle = _require_visible(db, principal, vehicle_id)
    now = _now()
    events = repository.latest_per_vehicle(db, [vehicle.id], include_simulated=True)
    return _vehicle_rows([vehicle], events, now=now, settings=settings)


def list_history(
    db: Session,
    principal: Principal,
    vehicle_id: uuid.UUID,
    params: PageParams,
    *,
    since: dt.datetime | None,
    until: dt.datetime | None,
    source: LocationSource | None,
    include_simulated: bool,
) -> Page[LocationOut]:
    _require_visible(db, principal, vehicle_id)
    rows, total = repository.list_events(
        db,
        vehicle_id,
        params,
        since=since,
        until=until,
        source=source,
        include_simulated=include_simulated,
    )
    return Page.build(
        [LocationOut.model_validate(r, from_attributes=True) for r in rows], total, params
    )


# --------------------------------------------------------------------------- ingestion


def _validate_point(payload: LocationReport | SimulatedLocation) -> None:
    if payload.latitude == 0 and payload.longitude == 0:
        raise UnprocessableError(
            "Coordinates 0,0 are not accepted: they are the usual placeholder of a device "
            "without a GPS fix"
        )


def _store(
    db: Session,
    *,
    vehicle: FleetVehicle,
    payload: LocationReport | SimulatedLocation,
    source: LocationSource,
    recorded_at: dt.datetime,
    user_id: uuid.UUID,
    task_id: uuid.UUID | None,
    plan_id: uuid.UUID | None,
) -> IngestResult:
    duplicate = repository.find_duplicate(
        db,
        vehicle_id=vehicle.id,
        source=source,
        recorded_at=recorded_at,
        sequence=payload.sequence,
    )
    if duplicate is not None:
        return IngestResult(
            duplicate=True, event=LocationOut.model_validate(duplicate, from_attributes=True)
        )
    newest = repository.latest_recorded_at(
        db, vehicle.id, simulated=source is LocationSource.SIMULATOR
    )
    quality = (
        LocationQuality.OUT_OF_ORDER
        if newest is not None and recorded_at < newest
        else LocationQuality.ACCEPTED
    )
    try:
        with db.begin_nested():
            event = repository.add_event(
                db,
                vehicle_id=vehicle.id,
                latitude=payload.latitude,
                longitude=payload.longitude,
                recorded_at=recorded_at,
                source=source,
                quality=quality,
                accuracy_m=payload.accuracy_m,
                speed_kph=payload.speed_kph,
                heading_deg=payload.heading_deg,
                sequence=payload.sequence,
                collection_task_id=task_id,
                route_plan_id=plan_id,
                reported_by_id=user_id,
            )
    except IntegrityError:
        # A concurrent retry stored the same event between our check and our insert.
        existing = repository.find_duplicate(
            db,
            vehicle_id=vehicle.id,
            source=source,
            recorded_at=recorded_at,
            sequence=payload.sequence,
        )
        if existing is None:
            raise
        return IngestResult(
            duplicate=True, event=LocationOut.model_validate(existing, from_attributes=True)
        )
    return IngestResult(
        duplicate=False, event=LocationOut.model_validate(event, from_attributes=True)
    )


def _resolve_links(
    db: Session,
    principal: Principal,
    vehicle: FleetVehicle,
    payload: LocationReport | SimulatedLocation,
    *,
    must_be_working: bool,
) -> tuple[uuid.UUID | None, uuid.UUID | None]:
    task_id = payload.collection_task_id
    if must_be_working:
        working = repository.working_tasks_on_vehicle(db, principal.user_id, vehicle.id)
        if task_id is not None and task_id not in {t.id for t in working}:
            raise UnprocessableError(
                "collection_task_id must be an open task of yours that uses this vehicle"
            )
        if task_id is None:
            in_progress = [t for t in working if t.status is CollectionTaskStatus.IN_PROGRESS]
            if len(in_progress) == 1:  # unambiguous: link it, otherwise leave the event unlinked
                task_id = in_progress[0].id
    elif task_id is not None and collection.get(db, task_id) is None:
        raise UnprocessableError("collection_task_id does not refer to an existing task")
    plan_id = payload.route_plan_id
    if plan_id is not None:
        plan = plans.get(db, plan_id)
        if plan is None or plan.vehicle_id != vehicle.id:
            raise UnprocessableError("route_plan_id must be a plan that uses this vehicle")
    return task_id, plan_id


def report_location(
    db: Session,
    principal: Principal,
    settings: Settings,
    vehicle_id: uuid.UUID,
    payload: LocationReport,
    *,
    context: RequestContext,
) -> IngestResult:
    source = LocationSource(payload.source)
    vehicle = fleet.get(db, vehicle_id)
    if vehicle is None:
        raise NotFoundError("Vehicle not found")
    imported = source is LocationSource.IMPORTED
    if imported and not principal.has(MANAGE):
        raise ForbiddenError("Importing a track needs the fleet:manage permission")
    if not imported:
        if not principal.has("fleet:track"):
            raise ForbiddenError("Reporting positions needs the fleet:track permission")
        if vehicle.id not in repository.assigned_vehicle_ids(db, principal.user_id):
            raise NotAssignedToVehicleError(
                "You can report positions only for a vehicle that one of your open tasks uses"
            )
    if vehicle.status is VehicleStatus.RETIRED:
        raise VehicleRetiredError("A retired vehicle cannot report positions")
    _validate_point(payload)

    now = _now()
    recorded_at = _utc(payload.recorded_at)
    if recorded_at > now + dt.timedelta(seconds=settings.tracking_max_future_skew_seconds):
        raise UnprocessableError("recorded_at is in the future (check the device clock)")
    if imported:
        if recorded_at > now - dt.timedelta(seconds=settings.tracking_stale_after_seconds):
            raise UnprocessableError(
                "An imported track must be historical: recorded_at has to be older than the "
                "stale threshold. Recent positions come from the vehicle's own reports."
            )
    elif recorded_at < now - dt.timedelta(hours=settings.tracking_max_report_age_hours):
        raise UnprocessableError(
            f"recorded_at is older than {settings.tracking_max_report_age_hours} hours; "
            "older positions can only be imported by a manager"
        )

    if repository.count_since(db, vehicle.id, now - dt.timedelta(minutes=1)) >= (
        settings.tracking_max_events_per_minute
    ):
        raise TooManyRequestsError(
            "Too many position reports for this vehicle; slow down",
            headers={"Retry-After": "10"},
        )
    task_id, plan_id = _resolve_links(db, principal, vehicle, payload, must_be_working=not imported)
    result = _store(
        db,
        vehicle=vehicle,
        payload=payload,
        source=source,
        recorded_at=recorded_at,
        user_id=principal.user_id,
        task_id=task_id,
        plan_id=plan_id,
    )
    if imported and not result.duplicate:
        # Positions from devices are too frequent to audit one by one; imports are rare and
        # change what the history says, so each one is recorded.
        audit.record(
            db,
            action="tracking.location_imported",
            entity_type="vehicle",
            entity_id=vehicle.id,
            actor_id=principal.user_id,
            context=context,
            changes={"event_id": str(result.event.id), "recorded_at": recorded_at.isoformat()},
        )
    db.commit()
    return result


# --------------------------------------------------------------------------- simulator


def _require_simulator(settings: Settings) -> None:
    if not settings.simulator_enabled:
        raise SimulatorDisabledError("The tracking simulator is disabled in this environment")


def simulate_location(
    db: Session,
    principal: Principal,
    settings: Settings,
    vehicle_id: uuid.UUID,
    payload: SimulatedLocation,
) -> IngestResult:
    _require_simulator(settings)
    vehicle = fleet.get(db, vehicle_id)
    if vehicle is None:
        raise NotFoundError("Vehicle not found")
    if vehicle.status is VehicleStatus.RETIRED:
        raise VehicleRetiredError("A retired vehicle cannot report positions")
    _validate_point(payload)
    now = _now()
    recorded_at = _utc(payload.recorded_at) if payload.recorded_at else now
    if recorded_at > now + dt.timedelta(seconds=settings.tracking_max_future_skew_seconds):
        raise UnprocessableError("recorded_at is in the future")
    _, plan_id = _resolve_links(db, principal, vehicle, payload, must_be_working=False)
    result = _store(
        db,
        vehicle=vehicle,
        payload=payload,
        source=LocationSource.SIMULATOR,
        recorded_at=recorded_at,
        user_id=principal.user_id,
        task_id=None,  # the simulator never attaches itself to real collection tasks
        plan_id=plan_id,
    )
    db.commit()
    return result


def reset_simulation(
    db: Session,
    principal: Principal,
    settings: Settings,
    vehicle_id: uuid.UUID,
    *,
    context: RequestContext,
) -> int:
    _require_simulator(settings)
    if fleet.get(db, vehicle_id) is None:
        raise NotFoundError("Vehicle not found")
    removed = repository.delete_simulated(db, vehicle_id)
    audit.record(
        db,
        action="tracking.simulation_reset",
        entity_type="vehicle",
        entity_id=vehicle_id,
        actor_id=principal.user_id,
        context=context,
        changes={"removed_events": removed},
    )
    db.commit()
    return removed


# --------------------------------------------------------------------------- retention


def purge_expired(db: Session, settings: Settings, *, now: dt.datetime | None = None) -> int:
    cutoff = (now or _now()) - dt.timedelta(days=settings.tracking_retention_days)
    removed = repository.purge_before(db, cutoff)
    audit.record(
        db,
        action="tracking.retention_purge",
        entity_type="vehicle_location_events",
        changes={"removed_events": removed, "older_than": cutoff.isoformat()},
    )
    db.commit()
    return removed


# --------------------------------------------------------------------------- map views


def _path(events: list[VehicleLocationEvent]) -> tuple[list[PathPoint], bool]:
    truncated = len(events) > PATH_LIMIT
    if truncated:
        events = events[1:]
    return (
        [
            PathPoint(
                latitude=e.latitude,
                longitude=e.longitude,
                recorded_at=e.recorded_at,
                source=e.source,
            )
            for e in events
        ],
        truncated,
    )


def collection_tracking(
    db: Session, principal: Principal, settings: Settings, task_id: uuid.UUID
) -> CollectionTracking:
    task = collection.get(db, task_id)
    if task is None:
        raise NotFoundError("Collection task not found")
    assignment = collection.active_assignment(db, task.id)
    is_assignee = assignment is not None and assignment.assignee_id == principal.user_id
    if not (principal.has("collection:manage") or is_assignee):
        raise ForbiddenError("Only managers and the assigned collector can track a collection")
    vehicle_id = assignment.vehicle_id if assignment else repository.task_vehicle_id(db, task.id)
    vehicle_row: VehiclePosition | None = None
    path: list[PathPoint] = []
    truncated = False
    if vehicle_id is not None:
        vehicle = fleet.get(db, vehicle_id)
        if vehicle is not None:
            now = _now()
            events = repository.latest_per_vehicle(db, [vehicle.id], include_simulated=False)
            rows = _vehicle_rows([vehicle], events, now=now, settings=settings)
            vehicle_row = next((r for r in rows if not r.simulated), None)
            path, truncated = _path(
                repository.path(db, vehicle.id, simulated=False, limit=PATH_LIMIT, task_id=task.id)
            )
    return CollectionTracking(
        task_id=task.id,
        title=task.title,
        status=task.status.value,
        latitude=task.latitude,
        longitude=task.longitude,
        destination_facility_id=task.destination_facility_id,
        vehicle_id=vehicle_id,
        vehicle=vehicle_row,
        path=path,
        path_truncated=truncated,
    )


def route_tracking(
    db: Session,
    principal: Principal,
    settings: Settings,
    plan_id: uuid.UUID,
    *,
    include_simulated: bool,
) -> RouteTracking:
    plan = plans.get(db, plan_id)
    if plan is None:
        raise NotFoundError("Route plan not found")
    detail = plan_service.get_plan(db, plan_id)
    task_ids = [s.collection_task_id for s in detail.stops if s.collection_task_id]
    statuses = repository.task_statuses(db, task_ids)
    stops = [
        StopProgress(
            sequence=s.sequence,
            kind=s.kind,
            label=s.label,
            latitude=s.latitude,
            longitude=s.longitude,
            task_id=s.collection_task_id,
            task_status=statuses[s.collection_task_id].value
            if s.collection_task_id in statuses
            else None,
            completed=statuses.get(s.collection_task_id) is CollectionTaskStatus.COMPLETED
            if s.collection_task_id
            else False,
        )
        for s in detail.stops
    ]
    task_stops = [s for s in stops if s.kind == "task"]
    visible = _visible_vehicle_ids(db, principal)
    vehicle_row: VehiclePosition | None = None
    path: list[PathPoint] = []
    truncated = False
    path_simulated = False
    if plan.vehicle_id is not None and (visible is None or plan.vehicle_id in visible):
        vehicle = fleet.get(db, plan.vehicle_id)
        if vehicle is not None:
            now = _now()
            events = repository.latest_per_vehicle(
                db, [vehicle.id], include_simulated=include_simulated
            )
            rows = _vehicle_rows([vehicle], events, now=now, settings=settings)
            # A simulated position wins only when asked for and no real one exists.
            real = next((r for r in rows if not r.simulated and r.position), None)
            sim = next((r for r in rows if r.simulated), None)
            vehicle_row = real or sim or rows[0]
            path_simulated = vehicle_row.simulated
            day_start = dt.datetime.combine(plan.planned_date, dt.time.min, tzinfo=dt.UTC)
            path, truncated = _path(
                repository.path(
                    db,
                    vehicle.id,
                    simulated=path_simulated,
                    limit=PATH_LIMIT,
                    since=day_start,
                    until=day_start + dt.timedelta(days=1),
                )
            )
    return RouteTracking(
        route_plan_id=plan.id,
        plan_status=plan.status.value,
        vehicle_id=plan.vehicle_id,
        stops=stops,
        completed_task_stops=sum(1 for s in task_stops if s.completed),
        total_task_stops=len(task_stops),
        vehicle=vehicle_row,
        path=path,
        path_simulated=path_simulated,
        path_truncated=truncated,
    )
