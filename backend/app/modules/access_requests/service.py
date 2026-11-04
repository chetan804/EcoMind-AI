"""Role requests: a signed-in person asks for an operational role, an administrator decides.

Nobody can obtain a privileged role by choosing it: public registration always yields
``citizen`` (see ``users/rbac.py``). Approval *adds* the requested role next to the existing ones
and is the only way this module changes roles. Every step is audited and the requester is
notified. An administrator cannot decide their own request, and the ``administrator`` role cannot
be requested at all.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.access_requests import repository
from app.modules.access_requests.constants import RequestableRole, RequestStatus
from app.modules.access_requests.models import RoleRequest
from app.modules.access_requests.schemas import DecisionRequest, RoleRequestCreate, RoleRequestOut
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.notifications import service as notifications
from app.modules.notifications.constants import NotificationCategory
from app.modules.users import repository as users
from app.modules.users.models import User


class AlreadyPendingError(ConflictError):
    code = "role_request_pending"


class AlreadyHeldError(ConflictError):
    code = "role_already_held"


class AlreadyDecidedError(ConflictError):
    code = "role_request_decided"


def _out(row: RoleRequest, user: User) -> RoleRequestOut:
    return RoleRequestOut(
        id=row.id,
        user_id=row.user_id,
        requester_email=user.email,
        requester_name=user.full_name,
        requested_role=row.requested_role,
        status=row.status,
        reason=row.reason,
        organisation=row.organisation,
        decided_by_id=row.decided_by_id,
        decided_at=row.decided_at,
        decision_note=row.decision_note,
        created_at=row.created_at,
    )


def create(
    db: Session, principal: Principal, payload: RoleRequestCreate, *, context: RequestContext
) -> RoleRequestOut:
    role = payload.requested_role.value
    if role in principal.roles:
        raise AlreadyHeldError(f"You already hold the {role} role")
    if repository.pending_for_user(db, principal.user_id) is not None:
        raise AlreadyPendingError("You already have a role request waiting for a decision")
    user = users.get_by_id(db, principal.user_id)
    if user is None:  # the account vanished between authentication and now
        raise NotFoundError("User not found")
    try:
        row = repository.add(
            db,
            user_id=principal.user_id,
            requested_role=payload.requested_role,
            reason=payload.reason,
            organisation=payload.organisation,
        )
    except IntegrityError as exc:  # lost a race with a second submission by the same person
        db.rollback()
        raise AlreadyPendingError("You already have a role request waiting for a decision") from exc
    audit.record(
        db,
        action="access_request.created",
        entity_type="role_request",
        entity_id=row.id,
        actor_id=principal.user_id,
        context=context,
        changes={"requested_role": role},
    )
    db.commit()
    db.refresh(row)
    return _out(row, user)


def list_mine(db: Session, principal: Principal) -> list[RoleRequestOut]:
    user = users.get_by_id(db, principal.user_id)
    if user is None:
        raise NotFoundError("User not found")
    return [_out(r, user) for r in repository.list_for_user(db, principal.user_id)]


def withdraw(
    db: Session, principal: Principal, request_id: uuid.UUID, *, context: RequestContext
) -> RoleRequestOut:
    row = repository.get(db, request_id, for_update=True)
    # Someone else's request looks exactly like a missing one.
    if row is None or row.user_id != principal.user_id:
        db.rollback()
        raise NotFoundError("Role request not found")
    if row.status != RequestStatus.PENDING:
        db.rollback()
        raise AlreadyDecidedError("This request is no longer waiting for a decision")
    row.status = RequestStatus.WITHDRAWN
    audit.record(
        db,
        action="access_request.withdrawn",
        entity_type="role_request",
        entity_id=row.id,
        actor_id=principal.user_id,
        context=context,
    )
    db.commit()
    user = users.get_by_id(db, row.user_id)
    assert user is not None  # noqa: S101 - foreign key guarantees it
    return _out(row, user)


def list_all(
    db: Session,
    params: PageParams,
    *,
    status: RequestStatus | None,
    role: RequestableRole | None,
) -> Page[RoleRequestOut]:
    rows, total = repository.list_page(db, params, status=status, role=role)
    return Page.build([_out(r, u) for r, u in rows], total, params)


def decide(
    db: Session,
    principal: Principal,
    request_id: uuid.UUID,
    payload: DecisionRequest,
    *,
    context: RequestContext,
) -> RoleRequestOut:
    row = repository.get(db, request_id, for_update=True)
    if row is None:
        db.rollback()
        raise NotFoundError("Role request not found")
    if row.user_id == principal.user_id:
        db.rollback()
        raise ForbiddenError("You cannot decide your own role request")
    if row.status != RequestStatus.PENDING:
        db.rollback()
        raise AlreadyDecidedError("This request has already been decided or withdrawn")
    if not payload.approve and not payload.note:
        db.rollback()
        raise ConflictError("Give the person a reason when rejecting a request")
    user = users.get_by_id(db, row.user_id)
    if user is None:
        db.rollback()
        raise NotFoundError("User not found")

    role_name = row.requested_role.value
    now = dt.datetime.now(dt.UTC)
    row.status = RequestStatus.APPROVED if payload.approve else RequestStatus.REJECTED
    row.decided_by_id = principal.user_id
    row.decided_at = now
    row.decision_note = payload.note
    changes: dict[str, object] = {"requested_role": role_name, "note": payload.note}
    if payload.approve:
        before = users.role_names(db, user.id)
        if role_name not in before:
            role = users.get_role_by_name(db, role_name)
            if role is None:  # migrations were not applied: fail loudly, never grant silently
                raise RuntimeError(f"Role {role_name!r} is missing; run database migrations")
            users.assign_role(db, user_id=user.id, role_id=role.id)
        changes["roles_after"] = sorted({*before, role_name})
    audit.record(
        db,
        action="access_request.approved" if payload.approve else "access_request.rejected",
        entity_type="role_request",
        entity_id=row.id,
        actor_id=principal.user_id,
        context=context,
        changes=changes,
    )
    label = role_name.replace("_", " ")
    notifications.notify(
        db,
        recipient_id=user.id,
        category=NotificationCategory.SYSTEM,
        title=f"Your {label} role request was {'approved' if payload.approve else 'declined'}",
        body=payload.note,
        entity_type="role_request",
        entity_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return _out(row, user)
