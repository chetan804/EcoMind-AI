"""Fleet use cases. Reading needs ``fleet:read``; changing needs ``fleet:manage``."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import AppError, NotFoundError, UnprocessableError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.facilities import repository as facilities
from app.modules.fleet import repository
from app.modules.fleet.constants import VehicleStatus, VehicleType
from app.modules.fleet.models import FleetVehicle
from app.modules.fleet.schemas import VehicleCreate, VehicleOut, VehicleUpdate

# A vehicle in one of these states cannot be given new work.
UNASSIGNABLE = frozenset({VehicleStatus.MAINTENANCE, VehicleStatus.RETIRED})


class RegistrationTakenError(AppError):
    status_code = 409
    code = "vehicle_registration_taken"


class VehicleInUseError(AppError):
    status_code = 409
    code = "vehicle_in_use"


def _out(vehicle: FleetVehicle, active: int) -> VehicleOut:
    out = VehicleOut.model_validate(vehicle, from_attributes=True)
    out.active_task_count = active
    return out


def _require_facility(db: Session, facility_id: uuid.UUID | None) -> None:
    if facility_id is not None and facilities.get(db, facility_id) is None:
        raise UnprocessableError("home_facility_id does not refer to an existing facility")


def list_vehicles(
    db: Session,
    params: PageParams,
    *,
    vehicle_type: VehicleType | None,
    status: VehicleStatus | None,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> Page[VehicleOut]:
    rows, total = repository.list_page(
        db, params, vehicle_type=vehicle_type, status=status, q=q, sort_by=sort_by, order=order
    )
    counts = repository.active_task_counts(db, [v.id for v in rows])
    return Page.build([_out(v, counts.get(v.id, 0)) for v in rows], total, params)


def get_vehicle(db: Session, vehicle_id: uuid.UUID) -> VehicleOut:
    vehicle = repository.get(db, vehicle_id)
    if vehicle is None:
        raise NotFoundError("Vehicle not found")
    return _out(vehicle, repository.active_task_counts(db, [vehicle.id]).get(vehicle.id, 0))


def create_vehicle(
    db: Session, principal: Principal, payload: VehicleCreate, *, context: RequestContext
) -> VehicleOut:
    _require_facility(db, payload.home_facility_id)
    try:
        vehicle = repository.add(db, **payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        if "registration_number" not in str(exc.orig):
            raise
        raise RegistrationTakenError(
            f"A vehicle with registration {payload.registration_number} already exists"
        ) from exc
    audit.record(
        db,
        action="vehicle.created",
        entity_type="fleet_vehicle",
        entity_id=vehicle.id,
        actor_id=principal.user_id,
        context=context,
        changes={"registration_number": vehicle.registration_number},
    )
    db.commit()
    db.refresh(vehicle)
    return _out(vehicle, 0)


def update_vehicle(
    db: Session,
    principal: Principal,
    vehicle_id: uuid.UUID,
    payload: VehicleUpdate,
    *,
    context: RequestContext,
) -> VehicleOut:
    vehicle = repository.get(db, vehicle_id, for_update=True)
    if vehicle is None:
        raise NotFoundError("Vehicle not found")
    active = repository.active_task_counts(db, [vehicle.id]).get(vehicle.id, 0)
    changes: dict[str, Any] = {}
    for field in payload.model_fields_set:
        new, old = getattr(payload, field), getattr(vehicle, field)
        if new == old:
            continue
        if field == "home_facility_id":
            _require_facility(db, new)
        if field == "status" and new in UNASSIGNABLE and active:
            db.rollback()
            raise VehicleInUseError(
                f"Vehicle has {active} open collection task(s); reassign them before "
                f"setting status {new.value}"
            )
        changes[field] = {
            "from": str(getattr(old, "value", old)),
            "to": str(getattr(new, "value", new)),
        }
        setattr(vehicle, field, new)
    if not changes:
        return _out(vehicle, active)
    audit.record(
        db,
        action="vehicle.updated",
        entity_type="fleet_vehicle",
        entity_id=vehicle.id,
        actor_id=principal.user_id,
        context=context,
        changes={"fields": changes},
    )
    db.commit()
    db.refresh(vehicle)
    return _out(vehicle, active)
