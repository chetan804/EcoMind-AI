"""Database access for role requests. No business rules and no commits here."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.pagination import PageParams
from app.modules.access_requests.constants import RequestableRole, RequestStatus
from app.modules.access_requests.models import RoleRequest
from app.modules.users.models import User


def get(db: Session, request_id: uuid.UUID, *, for_update: bool = False) -> RoleRequest | None:
    stmt = select(RoleRequest).where(RoleRequest.id == request_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.execute(stmt).scalar_one_or_none()


def pending_for_user(db: Session, user_id: uuid.UUID) -> RoleRequest | None:
    return db.execute(
        select(RoleRequest).where(
            RoleRequest.user_id == user_id, RoleRequest.status == RequestStatus.PENDING
        )
    ).scalar_one_or_none()


def add(db: Session, **fields: object) -> RoleRequest:
    row = RoleRequest(**fields)
    db.add(row)
    db.flush()
    return row


def list_for_user(db: Session, user_id: uuid.UUID) -> list[RoleRequest]:
    return list(
        db.scalars(
            select(RoleRequest)
            .where(RoleRequest.user_id == user_id)
            .order_by(RoleRequest.created_at.desc())
            .limit(50)
        )
    )


def list_page(
    db: Session,
    params: PageParams,
    *,
    status: RequestStatus | None,
    role: RequestableRole | None,
) -> tuple[list[tuple[RoleRequest, User]], int]:
    base = select(RoleRequest, User).join(User, User.id == RoleRequest.user_id)
    count = select(func.count()).select_from(RoleRequest)
    if status is not None:
        base = base.where(RoleRequest.status == status)
        count = count.where(RoleRequest.status == status)
    if role is not None:
        base = base.where(RoleRequest.requested_role == role)
        count = count.where(RoleRequest.requested_role == role)
    rows = db.execute(
        base.order_by(RoleRequest.created_at.desc()).offset(params.offset).limit(params.limit)
    ).all()
    return [(r, u) for r, u in rows], db.execute(count).scalar_one()


def get_with_user(db: Session, request_id: uuid.UUID) -> tuple[RoleRequest, User] | None:
    row = db.execute(
        select(RoleRequest, User)
        .join(User, User.id == RoleRequest.user_id)
        .where(RoleRequest.id == request_id)
    ).first()
    return (row[0], row[1]) if row else None
