"""The reward catalogue and redemptions. Each public function commits its own transaction.

Staff (``rewards:manage``) enter the catalogue: the platform ships no rewards, partners or values.
A citizen spends ledger points on an item (``rewards:redeem``); staff hand the reward over and mark
it fulfilled, or cancel it, which refunds the points. Money side and hand-over side stay apart:

* the ledger gets a negative ``redeemed`` entry, and on cancellation a positive ``reversal`` that
  points back at it (append-only, like every other correction);
* ``reward_redemptions`` tracks pending / fulfilled / cancelled and the claim code.

Concurrency: the user row is locked first (the same lock the adjustments use, so a spend cannot
interleave with a debit), then the item row. Every function takes the locks in that order.
"""

from __future__ import annotations

import datetime as dt
import secrets
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.exceptions import AppError, NotFoundError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.notifications import service as notifications
from app.modules.notifications.constants import NotificationCategory
from app.modules.rewards import service
from app.modules.rewards.adjustments import InsufficientBalanceError
from app.modules.rewards.constants import (
    CODE_ALPHABET,
    CODE_LENGTH,
    LedgerEntryType,
    LedgerSourceType,
    RedemptionStatus,
)
from app.modules.rewards.models import RewardItem, RewardRedemption
from app.modules.rewards.schemas import (
    CancelOwnRequest,
    CatalogItemOut,
    FulfilRequest,
    ItemCreate,
    ItemOut,
    ItemUpdate,
    RedeemRequest,
    RedemptionOut,
)
from app.modules.users import repository as users
from app.modules.users.models import User


class RewardUnavailableError(AppError):
    status_code = 409
    code = "reward_unavailable"


class RedemptionLimitError(AppError):
    status_code = 409
    code = "redemption_limit_reached"


class ClientRequestIdReusedError(AppError):
    status_code = 409
    code = "client_request_id_reused"


class InvalidRedemptionStateError(AppError):
    status_code = 409
    code = "invalid_redemption_state"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _expired(item: RewardItem, now: dt.datetime) -> bool:
    return item.valid_until is not None and item.valid_until <= now


def _refuse(db: Session, error: AppError) -> AppError:
    """Release the locks taken so far before the error is raised."""
    db.rollback()
    return error


# -- items (staff) -------------------------------------------------------------------------------
def _counts(db: Session, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, tuple[int, int]]:
    if not item_ids:
        return {}
    rows = db.execute(
        select(
            RewardRedemption.item_id,
            func.count(),
            func.count().filter(RewardRedemption.status == RedemptionStatus.PENDING),
        )
        .where(
            RewardRedemption.item_id.in_(item_ids),
            RewardRedemption.status != RedemptionStatus.CANCELLED,
        )
        .group_by(RewardRedemption.item_id)
    ).all()
    return {item_id: (int(total), int(pending)) for item_id, total, pending in rows}


def _item_out(db: Session, items: list[RewardItem]) -> list[ItemOut]:
    counts = _counts(db, [item.id for item in items])
    return [
        ItemOut(
            id=item.id,
            name=item.name,
            description=item.description,
            points_cost=item.points_cost,
            stock=item.stock,
            max_per_user=item.max_per_user,
            active=item.active,
            valid_until=item.valid_until,
            redeemed_count=counts.get(item.id, (0, 0))[0],
            pending_count=counts.get(item.id, (0, 0))[1],
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


def list_items(db: Session, params: PageParams, *, active: bool | None) -> Page[ItemOut]:
    stmt = select(RewardItem)
    if active is not None:
        stmt = stmt.where(RewardItem.active == active)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(RewardItem.active.desc(), RewardItem.points_cost, RewardItem.id)
            .limit(params.limit)
            .offset(params.offset)
        ).scalars()
    )
    return Page.build(_item_out(db, rows), total, params)


def create_item(
    db: Session, principal: Principal, payload: ItemCreate, *, context: RequestContext
) -> ItemOut:
    item = RewardItem(created_by_id=principal.user_id, **payload.model_dump())
    db.add(item)
    db.flush()
    audit.record(
        db,
        action="reward_item.created",
        entity_type="reward_item",
        entity_id=item.id,
        actor_id=principal.user_id,
        context=context,
        changes={"points_cost": item.points_cost, "stock": item.stock, "active": item.active},
    )
    db.commit()
    db.refresh(item)
    return _item_out(db, [item])[0]


def update_item(
    db: Session,
    principal: Principal,
    item_id: uuid.UUID,
    payload: ItemUpdate,
    *,
    context: RequestContext,
) -> ItemOut:
    item = db.scalar(select(RewardItem).where(RewardItem.id == item_id).with_for_update())
    if item is None:
        raise NotFoundError("Reward item not found")
    changes: dict[str, Any] = {}
    for field in payload.model_fields_set:
        new = getattr(payload, field)
        old = getattr(item, field)
        if new == old:
            continue
        changes[field] = {
            "from": old.isoformat() if isinstance(old, dt.datetime) else old,
            "to": new.isoformat() if isinstance(new, dt.datetime) else new,
        }
        setattr(item, field, new)
    if changes:
        audit.record(
            db,
            action="reward_item.updated",
            entity_type="reward_item",
            entity_id=item.id,
            actor_id=principal.user_id,
            context=context,
            changes={"fields": changes},
        )
        db.commit()
        db.refresh(item)
    return _item_out(db, [item])[0]


# -- catalogue (citizens) ------------------------------------------------------------------------
def _used_by(db: Session, user_id: uuid.UUID, item_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not item_ids:
        return {}
    rows = db.execute(
        select(RewardRedemption.item_id, func.count())
        .where(
            RewardRedemption.user_id == user_id,
            RewardRedemption.item_id.in_(item_ids),
            RewardRedemption.status != RedemptionStatus.CANCELLED,
        )
        .group_by(RewardRedemption.item_id)
    ).all()
    return {item_id: int(count) for item_id, count in rows}


def catalog_for(db: Session, principal: Principal, params: PageParams) -> Page[CatalogItemOut]:
    """Active, unexpired items, cheapest first. Out-of-stock items are shown, marked unavailable."""
    now = _now()
    stmt = select(RewardItem).where(
        RewardItem.active.is_(True),
        (RewardItem.valid_until.is_(None)) | (RewardItem.valid_until > now),
    )
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.execute(
            stmt.order_by(RewardItem.points_cost, RewardItem.name, RewardItem.id)
            .limit(params.limit)
            .offset(params.offset)
        ).scalars()
    )
    used = _used_by(db, principal.user_id, [item.id for item in rows])
    items: list[CatalogItemOut] = []
    for item in rows:
        taken = used.get(item.id, 0)
        left = None if item.max_per_user is None else max(0, item.max_per_user - taken)
        reason: str | None = None
        if item.stock is not None and item.stock <= 0:
            reason = "out_of_stock"
        elif left == 0:
            reason = "limit_reached"
        items.append(
            CatalogItemOut(
                id=item.id,
                name=item.name,
                description=item.description,
                points_cost=item.points_cost,
                stock_remaining=item.stock,
                valid_until=item.valid_until,
                remaining_for_you=left,
                available=reason is None,
                unavailable_reason=reason,
            )
        )
    return Page.build(items, total, params)


# -- redemptions ---------------------------------------------------------------------------------
def _redemption_out(
    redemption: RewardRedemption, owner: tuple[str, str] | None = None
) -> RedemptionOut:
    return RedemptionOut(
        id=redemption.id,
        user_id=redemption.user_id,
        user_name=owner[0] if owner else None,
        user_email=owner[1] if owner else None,
        item_id=redemption.item_id,
        item_name=redemption.item_name,
        points_spent=redemption.points_spent,
        code=redemption.code,
        status=redemption.status,
        created_at=redemption.created_at,
        fulfilled_at=redemption.fulfilled_at,
        note=redemption.note,
        cancelled_at=redemption.cancelled_at,
        cancel_reason=redemption.cancel_reason,
    )


def _new_code(db: Session) -> str:
    for _ in range(10):
        raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        code = f"{raw[:5]}-{raw[5:]}"
        if db.scalar(select(RewardRedemption.id).where(RewardRedemption.code == code)) is None:
            return code
    raise AppError("A claim code could not be generated; please try again")


def redeem(
    db: Session,
    principal: Principal,
    item_id: uuid.UUID,
    payload: RedeemRequest,
    *,
    context: RequestContext,
) -> tuple[RedemptionOut, bool]:
    """Spend points on an item. Returns the redemption and whether it was newly created."""
    db.execute(users.lock_statement(principal.user_id))
    repeated = db.scalar(
        select(RewardRedemption).where(
            RewardRedemption.user_id == principal.user_id,
            RewardRedemption.client_request_id == payload.client_request_id,
        )
    )
    if repeated is not None:
        if repeated.item_id != item_id:
            raise _refuse(
                db,
                ClientRequestIdReusedError("This request id was already used for another reward"),
            )
        db.rollback()
        return _redemption_out(repeated), False

    item = db.scalar(select(RewardItem).where(RewardItem.id == item_id).with_for_update())
    now = _now()
    # Inactive and expired items do not exist as far as a citizen can tell.
    if item is None or not item.active or _expired(item, now):
        raise _refuse(db, NotFoundError("Reward not found"))
    if item.stock is not None and item.stock <= 0:
        raise _refuse(db, RewardUnavailableError("This reward is out of stock"))
    taken = _used_by(db, principal.user_id, [item.id]).get(item.id, 0)
    if item.max_per_user is not None and taken >= item.max_per_user:
        raise _refuse(
            db,
            RedemptionLimitError(f"You can redeem this reward at most {item.max_per_user} time(s)"),
        )
    balance = service.balance_of(db, principal.user_id)[0]
    if balance < item.points_cost:
        raise _refuse(
            db,
            InsufficientBalanceError(
                f"This reward costs {item.points_cost} points and your balance is {balance}"
            ),
        )

    redemption_id = uuid.uuid4()
    entry = service.append(
        db,
        user_id=principal.user_id,
        entry_type=LedgerEntryType.REDEEMED,
        points=-item.points_cost,
        source_type=LedgerSourceType.REWARD_REDEMPTION,
        source_id=redemption_id,
        created_by_id=principal.user_id,
        description=f"Redeemed: {item.name}",
    )
    redemption = RewardRedemption(
        id=redemption_id,
        user_id=principal.user_id,
        item_id=item.id,
        item_name=item.name,
        points_spent=item.points_cost,
        code=_new_code(db),
        client_request_id=payload.client_request_id,
        status=RedemptionStatus.PENDING,
        ledger_entry_id=entry.id,
    )
    db.add(redemption)
    if item.stock is not None:
        item.stock -= 1
    db.flush()
    audit.record(
        db,
        action="reward.redeemed",
        entity_type="reward_redemption",
        entity_id=redemption.id,
        actor_id=principal.user_id,
        context=context,
        changes={"item_id": str(item.id), "points": item.points_cost},
    )
    notifications.notify(
        db,
        recipient_id=principal.user_id,
        category=NotificationCategory.REWARD,
        title="Reward redeemed",
        body=f"{item.name}. Your claim code is {redemption.code}.",
        entity_type="reward_redemption",
        entity_id=redemption.id,
    )
    db.commit()
    db.refresh(redemption)
    return _redemption_out(redemption), True


def my_redemptions(db: Session, principal: Principal, params: PageParams) -> Page[RedemptionOut]:
    stmt = select(RewardRedemption).where(RewardRedemption.user_id == principal.user_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(RewardRedemption.created_at.desc(), RewardRedemption.id)
        .limit(params.limit)
        .offset(params.offset)
    ).scalars()
    return Page.build([_redemption_out(r) for r in rows], total, params)


def list_redemptions(
    db: Session,
    params: PageParams,
    *,
    status: RedemptionStatus | None,
    code: str | None,
    user_id: uuid.UUID | None,
) -> Page[RedemptionOut]:
    stmt = select(RewardRedemption, User.full_name, User.email).join(
        User, User.id == RewardRedemption.user_id
    )
    if status is not None:
        stmt = stmt.where(RewardRedemption.status == status)
    if code:
        stmt = stmt.where(RewardRedemption.code == code.strip().upper())
    if user_id is not None:
        stmt = stmt.where(RewardRedemption.user_id == user_id)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(RewardRedemption.created_at.desc(), RewardRedemption.id)
        .limit(params.limit)
        .offset(params.offset)
    ).all()
    return Page.build([_redemption_out(r, (name, email)) for r, name, email in rows], total, params)


def _load_pending(
    db: Session, redemption_id: uuid.UUID, *, owner_id: uuid.UUID | None
) -> RewardRedemption:
    """Lock user, then the redemption row; refuse anything that is no longer pending."""
    found = db.get(RewardRedemption, redemption_id)
    if found is None or (owner_id is not None and found.user_id != owner_id):
        raise NotFoundError("Redemption not found")
    db.execute(users.lock_statement(found.user_id))
    redemption = db.scalar(
        select(RewardRedemption)
        .where(RewardRedemption.id == redemption_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if redemption is None:  # pragma: no cover - rows are never deleted
        raise NotFoundError("Redemption not found")
    if redemption.status is not RedemptionStatus.PENDING:
        raise _refuse(
            db,
            InvalidRedemptionStateError(
                f"A {redemption.status.value} redemption cannot be changed"
            ),
        )
    return redemption


def fulfil(
    db: Session,
    principal: Principal,
    redemption_id: uuid.UUID,
    payload: FulfilRequest,
    *,
    context: RequestContext,
) -> RedemptionOut:
    redemption = _load_pending(db, redemption_id, owner_id=None)
    redemption.status = RedemptionStatus.FULFILLED
    redemption.fulfilled_at = _now()
    redemption.fulfilled_by_id = principal.user_id
    redemption.note = payload.note
    audit.record(
        db,
        action="reward.redemption_fulfilled",
        entity_type="reward_redemption",
        entity_id=redemption.id,
        actor_id=principal.user_id,
        context=context,
        changes={"user_id": str(redemption.user_id)},
    )
    notifications.notify(
        db,
        recipient_id=redemption.user_id,
        category=NotificationCategory.REWARD,
        title="Your reward was handed over",
        body=redemption.item_name,
        entity_type="reward_redemption",
        entity_id=redemption.id,
    )
    db.commit()
    db.refresh(redemption)
    return _redemption_out(redemption)


def cancel(
    db: Session,
    principal: Principal,
    redemption_id: uuid.UUID,
    reason: str | None,
    *,
    by_owner: bool,
    context: RequestContext,
) -> RedemptionOut:
    """Cancel a pending redemption: the points come back (a reversal row) and the stock too."""
    redemption = _load_pending(db, redemption_id, owner_id=principal.user_id if by_owner else None)
    item = db.scalar(
        select(RewardItem).where(RewardItem.id == redemption.item_id).with_for_update()
    )
    refund = service.append(
        db,
        user_id=redemption.user_id,
        entry_type=LedgerEntryType.REVERSAL,
        points=redemption.points_spent,
        source_type=LedgerSourceType.REWARD_REDEMPTION,
        source_id=redemption.id,
        reverses_entry_id=redemption.ledger_entry_id,
        created_by_id=principal.user_id,
        description=reason or "Redemption cancelled",
    )
    if item is not None and item.stock is not None:
        item.stock += 1
    redemption.status = RedemptionStatus.CANCELLED
    redemption.cancelled_at = _now()
    redemption.cancelled_by_id = principal.user_id
    redemption.cancel_reason = reason
    redemption.refund_entry_id = refund.id
    audit.record(
        db,
        action="reward.redemption_cancelled",
        entity_type="reward_redemption",
        entity_id=redemption.id,
        actor_id=principal.user_id,
        context=context,
        changes={"by_owner": by_owner, "refunded_points": redemption.points_spent},
    )
    if not by_owner:
        notifications.notify(
            db,
            recipient_id=redemption.user_id,
            category=NotificationCategory.REWARD,
            title="Your reward redemption was cancelled",
            body=(
                f"{redemption.item_name}: {reason}. {redemption.points_spent} points were returned."
            ),
            entity_type="reward_redemption",
            entity_id=redemption.id,
        )
    db.commit()
    db.refresh(redemption)
    return _redemption_out(redemption)


def cancel_own(
    db: Session,
    principal: Principal,
    redemption_id: uuid.UUID,
    payload: CancelOwnRequest,
    *,
    context: RequestContext,
) -> RedemptionOut:
    return cancel(db, principal, redemption_id, payload.reason, by_owner=True, context=context)
