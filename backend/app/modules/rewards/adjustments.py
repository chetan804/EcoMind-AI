"""Manual ledger corrections (``rewards:manage``). Each function commits its own transaction.

The ledger is append-only (also enforced by a database trigger), so a correction is a new row:
an ``adjustment`` (signed points, with a mandatory reason) or a ``reversal`` that cancels one
earlier positive entry exactly once.
"""

from __future__ import annotations

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError, ConflictError, NotFoundError, UnprocessableError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.notifications import service as notifications
from app.modules.notifications.constants import NotificationCategory
from app.modules.rewards import service
from app.modules.rewards.constants import LedgerEntryType, LedgerSourceType
from app.modules.rewards.models import RewardLedgerEntry
from app.modules.rewards.schemas import AdjustmentCreate, ReverseRequest
from app.modules.users import repository as users


class InsufficientBalanceError(AppError):
    status_code = 409
    code = "insufficient_balance"


class AlreadyReversedError(AppError):
    status_code = 409
    code = "entry_already_reversed"


def adjust(
    db: Session, principal: Principal, payload: AdjustmentCreate, *, context: RequestContext
) -> RewardLedgerEntry:
    target = users.get_by_id(db, payload.user_id)
    if target is None or not target.is_active:
        raise UnprocessableError("user_id must refer to an active user")
    # Serialise balance changes per user so two concurrent debits cannot both pass the check.
    db.execute(users.lock_statement(target.id))
    if payload.points < 0:
        balance = service.balance_of(db, target.id)[0]
        if balance + payload.points < 0:
            db.rollback()
            raise InsufficientBalanceError(
                f"The adjustment would take the balance ({balance}) below zero"
            )
    entry = service.append(
        db,
        user_id=target.id,
        entry_type=LedgerEntryType.ADJUSTMENT,
        points=payload.points,
        source_type=LedgerSourceType.MANUAL,
        created_by_id=principal.user_id,
        description=payload.description,
    )
    audit.record(
        db,
        action="reward.adjusted",
        entity_type="reward_ledger_entry",
        entity_id=entry.id,
        actor_id=principal.user_id,
        context=context,
        changes={"user_id": str(target.id), "points": payload.points},
    )
    notifications.notify(
        db,
        recipient_id=target.id,
        category=NotificationCategory.REWARD,
        title="Your reward balance was adjusted",
        body=payload.description,
        entity_type="reward_ledger_entry",
        entity_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return entry


def reverse(
    db: Session,
    principal: Principal,
    entry_id: uuid.UUID,
    payload: ReverseRequest,
    *,
    context: RequestContext,
) -> RewardLedgerEntry:
    original = service.get_entry(db, entry_id)
    if original is None:
        raise NotFoundError("Ledger entry not found")
    db.execute(users.lock_statement(original.user_id))
    if original.entry_type is LedgerEntryType.REVERSAL or original.points <= 0:
        db.rollback()
        raise UnprocessableError("Only an earned or positive adjustment entry can be reversed")
    if service.reversal_of(db, original.id) is not None:
        db.rollback()
        raise AlreadyReversedError("This entry has already been reversed")
    try:
        entry = service.append(
            db,
            user_id=original.user_id,
            entry_type=LedgerEntryType.REVERSAL,
            points=-original.points,
            impact_weight_kg=original.impact_weight_kg,
            source_type=original.source_type,
            source_id=original.source_id,
            reverses_entry_id=original.id,
            created_by_id=principal.user_id,
            description=payload.reason,
        )
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("The entry could not be reversed") from exc
    audit.record(
        db,
        action="reward.reversed",
        entity_type="reward_ledger_entry",
        entity_id=entry.id,
        actor_id=principal.user_id,
        context=context,
        changes={"reverses": str(original.id), "points": entry.points},
    )
    notifications.notify(
        db,
        recipient_id=original.user_id,
        category=NotificationCategory.REWARD,
        title="A reward entry was reversed",
        body=payload.reason,
        entity_type="reward_ledger_entry",
        entity_id=entry.id,
    )
    db.commit()
    db.refresh(entry)
    return entry
