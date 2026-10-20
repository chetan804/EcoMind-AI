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
from app.modules.facilities.constants import FacilityStatus, FacilityType
from app.modules.facilities.models import Facility
from app.modules.facilities.schemas import FacilityCreate, FacilityOut, FacilityUpdate

MANAGE = "facilities:manage"
_SENSITIVE_FIELDS = frozenset({"contact_email"})


class FacilityCodeTakenError(AppError):
    status_code = 409
    code = "facility_code_taken"


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
        changes={"code": facility.code, "facility_type": facility.facility_type.value},
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
