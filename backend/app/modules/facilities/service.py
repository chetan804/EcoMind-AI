"""Facility use cases. Reading needs ``facilities:read``; changing needs ``facilities:manage``."""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import AppError, NotFoundError, UnprocessableError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.facilities import repository
from app.modules.facilities.constants import FacilityStatus, FacilityType, ZoneType
from app.modules.facilities.models import Facility, Zone
from app.modules.facilities.schemas import (
    FacilityCreate,
    FacilityOut,
    FacilityUpdate,
    ZoneCreate,
    ZoneOut,
    ZoneUpdate,
)

MANAGE = "facilities:manage"
_SENSITIVE_FIELDS = frozenset({"contact_email"})


class FacilityCodeTakenError(AppError):
    status_code = 409
    code = "facility_code_taken"


def _require_assignable_zone(db: Session, zone_id: uuid.UUID | None) -> None:
    """A facility may only be put in an existing, active zone (leaving a zone is always allowed)."""
    if zone_id is None:
        return
    zone = repository.get_zone(db, zone_id)
    if zone is None or not zone.is_active:
        raise UnprocessableError("zone_id must refer to an existing, active zone")


def _out(facility: Facility, principal: Principal) -> FacilityOut:
    out = FacilityOut.model_validate(facility, from_attributes=True)
    if not principal.has(MANAGE):
        out.contact_email = None
    return out


def list_facilities(
    db: Session,
    principal: Principal,
    params: PageParams,
    *,
    facility_type: FacilityType | None,
    status: FacilityStatus | None,
    city: str | None,
    zone_id: uuid.UUID | None,
    unzoned: bool,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> Page[FacilityOut]:
    rows, total = repository.list_page(
        db,
        params,
        facility_type=facility_type,
        status=status,
        city=city,
        zone_id=zone_id,
        unzoned=unzoned,
        q=q,
        sort_by=sort_by,
        order=order,
    )
    return Page.build([_out(f, principal) for f in rows], total, params)


def get_facility(db: Session, principal: Principal, facility_id: uuid.UUID) -> FacilityOut:
    facility = repository.get(db, facility_id)
    if facility is None:
        raise NotFoundError("Facility not found")
    return _out(facility, principal)


def create_facility(
    db: Session, principal: Principal, payload: FacilityCreate, *, context: RequestContext
) -> FacilityOut:
    _require_assignable_zone(db, payload.zone_id)
    try:
        facility = repository.add(db, **payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        # The only unique column besides the id is ``code``; anything else is a real fault.
        if "uq_facilities_code" not in str(exc.orig):
            raise
        raise FacilityCodeTakenError(f"A facility with code {payload.code} already exists") from exc
    audit.record(
        db,
        action="facility.created",
        entity_type="facility",
        entity_id=facility.id,
        actor_id=principal.user_id,
        context=context,
        changes={
            "code": facility.code,
            "facility_type": facility.facility_type.value,
            **({"zone_id": str(facility.zone_id)} if facility.zone_id else {}),
        },
    )
    db.commit()
    db.refresh(facility)
    return _out(facility, principal)


def _plain(value: object) -> object:
    """A JSON-safe rendering of a column value for the audit trail."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    return str(value)


def update_facility(
    db: Session,
    principal: Principal,
    facility_id: uuid.UUID,
    payload: FacilityUpdate,
    *,
    context: RequestContext,
) -> FacilityOut:
    facility = repository.get(db, facility_id, for_update=True)
    if facility is None:
        raise NotFoundError("Facility not found")
    if "zone_id" in payload.model_fields_set and payload.zone_id != facility.zone_id:
        _require_assignable_zone(db, payload.zone_id)
    changes: dict[str, Any] = {}
    for field in payload.model_fields_set:
        new = getattr(payload, field)
        old = getattr(facility, field)
        if new == old:
            continue
        changes[field] = (
            {"changed": True}
            if field in _SENSITIVE_FIELDS
            else {"from": _plain(old), "to": _plain(new)}
        )
        setattr(facility, field, new)
    if not changes:
        return _out(facility, principal)  # nothing to do: no write, no audit noise
    # The database also enforces this pair; checking here turns a client mistake into a 422.
    if (facility.latitude is None) != (facility.longitude is None):
        db.rollback()
        raise UnprocessableError("latitude and longitude must be set together")
    audit.record(
        db,
        action="facility.updated",
        entity_type="facility",
        entity_id=facility.id,
        actor_id=principal.user_id,
        context=context,
        changes={"fields": changes},
    )
    db.commit()
    db.refresh(facility)
    return _out(facility, principal)


# -- zones ---------------------------------------------------------------------------------------
class ZoneCodeTakenError(AppError):
    status_code = 409
    code = "zone_code_taken"


def _zone_out(zone: Zone, count: int) -> ZoneOut:
    fields = {
        name: getattr(zone, name) for name in ZoneOut.model_fields if name != "facility_count"
    }
    return ZoneOut(**fields, facility_count=count)


def list_zones(
    db: Session,
    params: PageParams,
    *,
    zone_type: ZoneType | None,
    active: bool | None,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> Page[ZoneOut]:
    rows, total = repository.list_zones(
        db, params, zone_type=zone_type, active=active, q=q, sort_by=sort_by, order=order
    )
    counts = repository.facility_counts(db, [z.id for z in rows])
    return Page.build([_zone_out(z, counts.get(z.id, 0)) for z in rows], total, params)


def get_zone(db: Session, zone_id: uuid.UUID) -> ZoneOut:
    zone = repository.get_zone(db, zone_id)
    if zone is None:
        raise NotFoundError("Zone not found")
    return _zone_out(zone, repository.facility_counts(db, [zone.id]).get(zone.id, 0))


def create_zone(
    db: Session, principal: Principal, payload: ZoneCreate, *, context: RequestContext
) -> ZoneOut:
    try:
        zone = repository.add_zone(db, **payload.model_dump())
    except IntegrityError as exc:
        db.rollback()
        if "uq_zones_code" not in str(exc.orig):
            raise
        raise ZoneCodeTakenError(f"A zone with code {payload.code} already exists") from exc
    audit.record(
        db,
        action="zone.created",
        entity_type="zone",
        entity_id=zone.id,
        actor_id=principal.user_id,
        context=context,
        changes={"code": zone.code, "zone_type": zone.zone_type.value},
    )
    db.commit()
    db.refresh(zone)
    return _zone_out(zone, 0)


def update_zone(
    db: Session,
    principal: Principal,
    zone_id: uuid.UUID,
    payload: ZoneUpdate,
    *,
    context: RequestContext,
) -> ZoneOut:
    zone = repository.get_zone(db, zone_id, for_update=True)
    if zone is None:
        raise NotFoundError("Zone not found")
    changes: dict[str, Any] = {}
    for field in payload.model_fields_set:
        new = getattr(payload, field)
        old = getattr(zone, field)
        if new == old:
            continue
        changes[field] = {"from": _plain(old), "to": _plain(new)}
        setattr(zone, field, new)
    if changes:
        audit.record(
            db,
            action="zone.updated",
            entity_type="zone",
            entity_id=zone.id,
            actor_id=principal.user_id,
            context=context,
            changes={"fields": changes},
        )
        db.commit()
        db.refresh(zone)
    return _zone_out(zone, repository.facility_counts(db, [zone.id]).get(zone.id, 0))
