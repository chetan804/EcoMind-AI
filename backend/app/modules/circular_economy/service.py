"""Recovery-record use cases.

Facility staff record what was processed (``circular_economy:manage``); a *different* person
verifies it (``circular_economy:verify``). Only verified records feed recovery metrics.
Records are never edited: a wrong record is rejected and a new one is entered.
"""

from __future__ import annotations

import datetime as dt
import decimal
import uuid

from sqlalchemy.orm import Session

from app.common.enums import SortOrder
from app.common.pagination import Page, PageParams
from app.core.exceptions import AppError, NotFoundError, UnprocessableError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.circular_economy import repository
from app.modules.circular_economy.constants import RecoveryMethod, VerificationStatus
from app.modules.circular_economy.schemas import (
    Breakdown,
    RecoveryCreate,
    RecoveryOut,
    RecoverySummary,
    VerifyRequest,
)
from app.modules.collection import repository as collection
from app.modules.collection.constants import CollectionTaskStatus
from app.modules.facilities import repository as facilities
from app.modules.facilities.constants import FacilityStatus
from app.modules.sorting_guide import repository as categories

CLOCK_SKEW = dt.timedelta(minutes=5)
_RATE = decimal.Decimal("0.0001")


class AlreadyDecidedError(AppError):
    status_code = 409
    code = "recovery_already_decided"


class SelfVerificationError(AppError):
    status_code = 403
    code = "self_verification_forbidden"


def rate(recovered: decimal.Decimal, input_: decimal.Decimal) -> decimal.Decimal | None:
    if input_ <= 0:
        return None
    return (recovered / input_).quantize(_RATE, rounding=decimal.ROUND_HALF_UP)


def create(
    db: Session, principal: Principal, payload: RecoveryCreate, *, context: RequestContext
) -> RecoveryOut:
    if payload.processed_at > dt.datetime.now(dt.UTC) + CLOCK_SKEW:
        raise UnprocessableError("processed_at cannot be in the future")
    facility = facilities.get(db, payload.facility_id)
    if facility is None or facility.status is not FacilityStatus.ACTIVE:
        raise UnprocessableError("facility_id must refer to an active facility")
    category = categories.get_category(db, payload.material_category_id)
    if category is None or not category.is_active:
        raise UnprocessableError("material_category_id must refer to an active category")
    if payload.collection_task_id is not None:
        task = collection.get(db, payload.collection_task_id)
        if task is None or task.status is not CollectionTaskStatus.COMPLETED:
            raise UnprocessableError("collection_task_id must refer to a completed task")
    record = repository.add(
        db,
        **payload.model_dump(),
        created_by_id=principal.user_id,
        verification_status=VerificationStatus.PENDING,
    )
    audit.record(
        db,
        action="recovery_record.created",
        entity_type="recovery_record",
        entity_id=record.id,
        actor_id=principal.user_id,
        context=context,
        changes={
            "facility_id": str(record.facility_id),
            "category": category.code,
            "input_weight_kg": str(record.input_weight_kg),
            "recovered_weight_kg": str(record.recovered_weight_kg),
        },
    )
    db.commit()
    db.refresh(record)
    return RecoveryOut.model_validate(record, from_attributes=True)


def get(db: Session, record_id: uuid.UUID) -> RecoveryOut:
    record = repository.get(db, record_id)
    if record is None:
        raise NotFoundError("Recovery record not found")
    return RecoveryOut.model_validate(record, from_attributes=True)


def list_records(
    db: Session,
    params: PageParams,
    *,
    facility_id: uuid.UUID | None,
    category_id: uuid.UUID | None,
    method: RecoveryMethod | None,
    status: VerificationStatus | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
    sort_by: str,
    order: SortOrder,
) -> Page[RecoveryOut]:
    rows, total = repository.list_page(
        db,
        params,
        facility_id=facility_id,
        category_id=category_id,
        method=method,
        status=status,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        order=order,
    )
    return Page.build(
        [RecoveryOut.model_validate(r, from_attributes=True) for r in rows], total, params
    )


def decide(
    db: Session,
    principal: Principal,
    record_id: uuid.UUID,
    payload: VerifyRequest,
    *,
    context: RequestContext,
) -> RecoveryOut:
    record = repository.get(db, record_id, for_update=True)
    if record is None:
        raise NotFoundError("Recovery record not found")
    if record.created_by_id == principal.user_id:
        db.rollback()
        raise SelfVerificationError("A record must be verified by someone other than its author")
    if record.verification_status is not VerificationStatus.PENDING:
        db.rollback()
        raise AlreadyDecidedError(f"Record is already {record.verification_status.value}")
    record.verification_status = VerificationStatus(payload.decision)
    record.verified_by_id = principal.user_id
    record.verified_at = dt.datetime.now(dt.UTC)
    if payload.notes:
        record.notes = (
            f"{record.notes}\n[{payload.decision}] {payload.notes}"
            if record.notes
            else (f"[{payload.decision}] {payload.notes}")
        )
    audit.record(
        db,
        action=f"recovery_record.{payload.decision}",
        entity_type="recovery_record",
        entity_id=record.id,
        actor_id=principal.user_id,
        context=context,
        changes={"decision": payload.decision},
    )
    db.commit()
    db.refresh(record)
    return RecoveryOut.model_validate(record, from_attributes=True)


def summary(
    db: Session,
    *,
    facility_id: uuid.UUID | None,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> RecoverySummary:
    def breakdown(group: str) -> list[Breakdown]:
        return [
            Breakdown(
                key=k,
                label=label,
                records=n,
                input_weight_kg=i,
                recovered_weight_kg=r,
                recovery_rate=rate(r, i),
            )
            for k, label, n, i, r in repository.verified_totals(
                db, group=group, facility_id=facility_id, date_from=date_from, date_to=date_to
            )
        ]

    by_category = breakdown("category")
    counts = repository.status_counts(
        db, facility_id=facility_id, date_from=date_from, date_to=date_to
    )
    total_in = sum((b.input_weight_kg for b in by_category), decimal.Decimal(0))
    total_out = sum((b.recovered_weight_kg for b in by_category), decimal.Decimal(0))
    return RecoverySummary(
        verified_records=counts.get(VerificationStatus.VERIFIED, 0),
        input_weight_kg=total_in,
        recovered_weight_kg=total_out,
        recovery_rate=rate(total_out, total_in),
        pending_records=counts.get(VerificationStatus.PENDING, 0),
        rejected_records=counts.get(VerificationStatus.REJECTED, 0),
        by_category=by_category,
        by_method=breakdown("method"),
    )
