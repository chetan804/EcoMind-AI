"""Material-passport use cases and the chain-of-custody state machine.

A passport identifies one batch of sorted material. Its custody events are append-only (also
enforced by a database trigger). Allowed successors::

    created    -> collected | transferred | received
    collected  -> transferred | received
    transferred-> transferred | received
    received   -> transferred | processed
    processed  -> verified              (needs a linked, verified recovery record)
    verified   -> (final: status becomes ``recovered``)

Writing needs ``passports:manage``; reading needs ``passports:read``.
"""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from itertools import pairwise

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import AppError, ConflictError, NotFoundError, UnprocessableError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.circular_economy import repository as recovery
from app.modules.circular_economy.constants import VerificationStatus
from app.modules.collection import repository as collection
from app.modules.collection.constants import CollectionTaskStatus
from app.modules.facilities import repository as facilities
from app.modules.facilities.constants import FacilityStatus
from app.modules.material_passports import repository
from app.modules.material_passports.constants import CustodyEventType as T
from app.modules.material_passports.constants import PassportStatus
from app.modules.material_passports.models import MaterialPassport
from app.modules.material_passports.schemas import (
    EventCreate,
    EventOut,
    Integrity,
    LinkRecovery,
    PassportCreate,
    PassportDetail,
    PassportOut,
)
from app.modules.sorting_guide import repository as categories

CLOCK_SKEW = dt.timedelta(minutes=5)
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I

SUCCESSORS: dict[T, frozenset[T]] = {
    T.CREATED: frozenset({T.COLLECTED, T.TRANSFERRED, T.RECEIVED}),
    T.COLLECTED: frozenset({T.TRANSFERRED, T.RECEIVED}),
    T.TRANSFERRED: frozenset({T.TRANSFERRED, T.RECEIVED}),
    T.RECEIVED: frozenset({T.TRANSFERRED, T.PROCESSED}),
    T.PROCESSED: frozenset({T.VERIFIED}),
    T.VERIFIED: frozenset(),
}


class InvalidCustodyEventError(AppError):
    status_code = 409
    code = "invalid_custody_event"


class PassportClosedError(AppError):
    status_code = 409
    code = "passport_closed"


def new_code() -> str:
    return "MP-" + "".join(secrets.choice(_ALPHABET) for _ in range(10))


def _active_facility(db: Session, facility_id: uuid.UUID, field: str) -> None:
    facility = facilities.get(db, facility_id)
    if facility is None or facility.status is not FacilityStatus.ACTIVE:
        raise UnprocessableError(f"{field} must refer to an active facility")


def create(
    db: Session, principal: Principal, payload: PassportCreate, *, context: RequestContext
) -> PassportDetail:
    category = categories.get_category(db, payload.material_category_id)
    if category is None or not category.is_active:
        raise UnprocessableError("material_category_id must refer to an active category")
    if payload.current_facility_id is not None:
        _active_facility(db, payload.current_facility_id, "current_facility_id")
    if payload.origin_collection_task_id is not None:
        task = collection.get(db, payload.origin_collection_task_id)
        if task is None or task.status is not CollectionTaskStatus.COMPLETED:
            raise UnprocessableError("origin_collection_task_id must refer to a completed task")
    passport: MaterialPassport | None = None
    for _attempt in range(3):  # a code collision is astronomically unlikely, but handle it
        try:
            with db.begin_nested():
                passport = repository.add(
                    db,
                    **payload.model_dump(),
                    passport_code=new_code(),
                    status=PassportStatus.ACTIVE,
                    created_by_id=principal.user_id,
                )
            break
        except IntegrityError:
            continue
    if passport is None:
        raise ConflictError("Could not allocate a unique passport code; retry")
    repository.add_event(
        db,
        material_passport_id=passport.id,
        sequence=1,
        event_type=T.CREATED,
        occurred_at=dt.datetime.now(dt.UTC),
        actor_id=principal.user_id,
        to_facility_id=payload.current_facility_id,
    )
    audit.record(
        db,
        action="material_passport.created",
        entity_type="material_passport",
        entity_id=passport.id,
        actor_id=principal.user_id,
        context=context,
        changes={"passport_code": passport.passport_code, "category": category.code},
    )
    db.commit()
    return _detail(db, passport)


def _detail(db: Session, passport: MaterialPassport) -> PassportDetail:
    base = PassportOut.model_validate(passport, from_attributes=True)
    return PassportDetail(
        **base.model_dump(),
        events=[
            EventOut.model_validate(e, from_attributes=True)
            for e in repository.events(db, passport.id)
        ],
    )


def get(db: Session, passport_id: uuid.UUID) -> PassportDetail:
    passport = repository.get(db, passport_id)
    if passport is None:
        raise NotFoundError("Material passport not found")
    return _detail(db, passport)


def get_by_code(db: Session, code: str) -> PassportDetail:
    passport = repository.get_by_code(db, code.strip().upper())
    if passport is None:
        raise NotFoundError("Material passport not found")
    return _detail(db, passport)


def list_passports(
    db: Session,
    params: PageParams,
    *,
    status: PassportStatus | None,
    category_id: uuid.UUID | None,
    facility_id: uuid.UUID | None,
    q: str | None,
    sort_by: str,
    order: SortOrder,
) -> Page[PassportOut]:
    rows, total = repository.list_page(
        db,
        params,
        status=status,
        category_id=category_id,
        facility_id=facility_id,
        q=q,
        sort_by=sort_by,
        order=order,
    )
    return Page.build(
        [PassportOut.model_validate(r, from_attributes=True) for r in rows], total, params
    )


def link_recovery(
    db: Session,
    principal: Principal,
    passport_id: uuid.UUID,
    payload: LinkRecovery,
    *,
    context: RequestContext,
) -> PassportDetail:
    passport = repository.get(db, passport_id, for_update=True)
    if passport is None:
        raise NotFoundError("Material passport not found")
    if passport.status in (PassportStatus.RECOVERED, PassportStatus.RETIRED):
        db.rollback()
        raise PassportClosedError(f"A {passport.status.value} passport cannot be changed")
    record = recovery.get(db, payload.recovery_record_id)
    if record is None:
        db.rollback()
        raise UnprocessableError("recovery_record_id does not refer to an existing record")
    if record.verification_status is VerificationStatus.REJECTED:
        db.rollback()
        raise UnprocessableError("A rejected recovery record cannot be linked")
    if record.material_category_id != passport.material_category_id:
        db.rollback()
        raise UnprocessableError("The recovery record is for a different material category")
    if repository.passport_for_recovery(db, record.id, exclude=passport.id) is not None:
        db.rollback()
        raise ConflictError("This recovery record is already linked to another passport")
    passport.recovery_record_id = record.id
    audit.record(
        db,
        action="material_passport.recovery_linked",
        entity_type="material_passport",
        entity_id=passport.id,
        actor_id=principal.user_id,
        context=context,
        changes={"recovery_record_id": str(record.id)},
    )
    db.commit()
    return _detail(db, passport)


def add_event(
    db: Session,
    principal: Principal,
    passport_id: uuid.UUID,
    payload: EventCreate,
    *,
    context: RequestContext,
) -> PassportDetail:
    passport = repository.get(db, passport_id, for_update=True)
    if passport is None:
        raise NotFoundError("Material passport not found")
    if passport.status in (PassportStatus.RECOVERED, PassportStatus.RETIRED):
        db.rollback()
        raise PassportClosedError(f"A {passport.status.value} passport takes no further events")
    chain = repository.events(db, passport.id)
    last = chain[-1]
    kind = payload.event_type
    if kind is T.CREATED or kind not in SUCCESSORS[last.event_type]:
        db.rollback()
        raise InvalidCustodyEventError(
            f"A {kind.value} event cannot follow {last.event_type.value}"
        )
    when = payload.occurred_at or dt.datetime.now(dt.UTC)
    if when.tzinfo is None:
        db.rollback()
        raise UnprocessableError("occurred_at must include a timezone offset")
    if when > dt.datetime.now(dt.UTC) + CLOCK_SKEW:
        db.rollback()
        raise UnprocessableError("occurred_at cannot be in the future")
    if when < last.occurred_at:
        db.rollback()
        raise UnprocessableError("occurred_at cannot be earlier than the previous event")

    from_id = payload.from_facility_id or passport.current_facility_id
    to_id = payload.to_facility_id
    if kind in (T.TRANSFERRED, T.RECEIVED) and to_id is None:
        db.rollback()
        raise UnprocessableError(f"to_facility_id is required for a {kind.value} event")
    if kind is T.TRANSFERRED and from_id == to_id:
        db.rollback()
        raise UnprocessableError("A transfer must go to a different facility")
    for fid, name in ((from_id, "from_facility_id"), (to_id, "to_facility_id")):
        if fid is not None:
            _active_facility(db, fid, name)

    if kind in (T.PROCESSED, T.VERIFIED) and passport.current_facility_id is None:
        db.rollback()
        raise InvalidCustodyEventError(f"A {kind.value} event needs the batch to be at a facility")
    if kind is T.VERIFIED:
        record = (
            recovery.get(db, passport.recovery_record_id) if passport.recovery_record_id else None
        )
        if record is None or record.verification_status is not VerificationStatus.VERIFIED:
            db.rollback()
            raise InvalidCustodyEventError(
                "A verified event needs a linked recovery record that has been verified"
            )

    repository.add_event(
        db,
        material_passport_id=passport.id,
        sequence=last.sequence + 1,
        event_type=kind,
        occurred_at=when,
        actor_id=principal.user_id,
        from_facility_id=from_id if kind in (T.TRANSFERRED, T.RECEIVED) else None,
        to_facility_id=to_id,
        notes=payload.notes,
    )
    if kind is T.RECEIVED:
        passport.current_facility_id = to_id
    elif kind is T.TRANSFERRED:
        passport.current_facility_id = None  # in transit until the receiving facility confirms
    elif kind is T.PROCESSED:
        passport.status = PassportStatus.IN_PROCESSING
    elif kind is T.VERIFIED:
        passport.status = PassportStatus.RECOVERED
    audit.record(
        db,
        action=f"material_passport.{kind.value}",
        entity_type="material_passport",
        entity_id=passport.id,
        actor_id=principal.user_id,
        context=context,
        changes={"sequence": last.sequence + 1, "status": passport.status.value},
    )
    db.commit()
    return _detail(db, passport)


def integrity(db: Session, passport_id: uuid.UUID) -> Integrity:
    passport = repository.get(db, passport_id)
    if passport is None:
        raise NotFoundError("Material passport not found")
    chain = repository.events(db, passport.id)
    problems: list[str] = []
    if not chain or chain[0].event_type is not T.CREATED:
        problems.append("the chain does not start with a created event")
    for index, event in enumerate(chain, start=1):
        if event.sequence != index:
            problems.append(f"sequence gap: expected {index}, found {event.sequence}")
            break
    for before, after in pairwise(chain):
        if after.event_type not in SUCCESSORS[before.event_type]:
            problems.append(
                f"{after.event_type.value} (#{after.sequence}) cannot follow "
                f"{before.event_type.value}"
            )
        if after.occurred_at < before.occurred_at:
            problems.append(f"event #{after.sequence} is dated before event #{before.sequence}")
    return Integrity(
        passport_code=passport.passport_code,
        valid=not problems,
        events=len(chain),
        problems=problems,
    )
