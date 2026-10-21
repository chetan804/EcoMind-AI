"""Support tickets: a person asks, staff answer. Each public function commits its own transaction.

Privacy: a ticket carries the assistant conversation only when its owner ticks "share"; staff
reading that transcript is itself audited. A person sees only their own tickets (someone else's
looks like a missing ticket); staff with ``support:manage`` see all.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.common.search import LIKE_ESCAPE, contains_pattern
from app.core.exceptions import AppError, BadRequestError, ConflictError, NotFoundError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.notifications import service as notifications
from app.modules.notifications.constants import NotificationCategory
from app.modules.support import assistant
from app.modules.support.constants import (
    MAX_OPEN_TICKETS_PER_USER,
    TICKET_TRANSITIONS,
    TicketStatus,
)
from app.modules.support.models import SupportTicket, SupportTicketReply
from app.modules.support.schemas import (
    ReplyCreate,
    ReplyOut,
    TicketCreate,
    TicketDetail,
    TicketOut,
    TicketUpdate,
)
from app.modules.users import repository as users
from app.modules.users.models import Permission, RolePermission, User, UserRole

_ACTIVE = (TicketStatus.OPEN, TicketStatus.IN_PROGRESS)
_STAFF_NOTIFY_LIMIT = 25


class TicketClosedError(AppError):
    status_code = 409
    code = "ticket_closed"


class InvalidTicketTransitionError(AppError):
    status_code = 409
    code = "invalid_ticket_transition"


class TooManyOpenTicketsError(AppError):
    status_code = 409
    code = "too_many_open_tickets"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def _staff_ids(db: Session) -> list[uuid.UUID]:
    stmt = (
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(RolePermission, RolePermission.role_id == UserRole.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(Permission.code == "support:manage", User.is_active.is_(True))
        .distinct()
        .order_by(User.id)
        .limit(_STAFF_NOTIFY_LIMIT)
    )
    return list(db.scalars(stmt))


def _notify(db: Session, recipient: uuid.UUID, title: str, ticket: SupportTicket) -> None:
    notifications.notify(
        db,
        recipient_id=recipient,
        category=NotificationCategory.SYSTEM,
        title=title,
        body=ticket.subject,
        entity_type="support_ticket",
        entity_id=ticket.id,
    )


def _load(
    db: Session, principal: Principal, ticket_id: uuid.UUID, *, lock: bool = False
) -> SupportTicket:
    stmt = select(SupportTicket).where(SupportTicket.id == ticket_id)
    if lock:
        stmt = stmt.with_for_update()
    ticket = db.scalar(stmt)
    if ticket is None or (
        ticket.user_id != principal.user_id and not principal.has("support:manage")
    ):
        raise NotFoundError("Ticket not found")
    return ticket


def _out(db: Session, tickets: list[SupportTicket], *, staff_view: bool) -> list[TicketOut]:
    if not tickets:
        return []
    ids = [t.id for t in tickets]
    reply_counts = {
        ticket_id: int(n)
        for ticket_id, n in db.execute(
            select(SupportTicketReply.ticket_id, func.count())
            .where(SupportTicketReply.ticket_id.in_(ids))
            .group_by(SupportTicketReply.ticket_id)
        )
    }
    user_ids = {t.user_id for t in tickets} | {t.assignee_id for t in tickets if t.assignee_id}
    names = {
        user_id: name
        for user_id, name in db.execute(
            select(User.id, User.full_name).where(User.id.in_(user_ids))
        )
    }
    return [
        TicketOut(
            id=t.id,
            user_id=t.user_id,
            requester_name=names.get(t.user_id) if staff_view else None,
            subject=t.subject,
            status=t.status,
            assignee_id=t.assignee_id,
            assignee_name=names.get(t.assignee_id) if t.assignee_id else None,
            reply_count=int(reply_counts.get(t.id, 0)),
            conversation_shared=t.shared_conversation_id is not None,
            created_at=t.created_at,
            updated_at=t.updated_at,
            resolved_at=t.resolved_at,
        )
        for t in tickets
    ]


def _detail(
    db: Session, principal: Principal, ticket: SupportTicket, *, context: RequestContext | None
) -> TicketDetail:
    staff_view = principal.has("support:manage")
    base = _out(db, [ticket], staff_view=staff_view)[0]
    replies = db.execute(
        select(SupportTicketReply, User.full_name)
        .join(User, User.id == SupportTicketReply.author_id)
        .where(SupportTicketReply.ticket_id == ticket.id)
        .order_by(SupportTicketReply.created_at, SupportTicketReply.id)
    ).all()
    conversation = None
    if ticket.shared_conversation_id is not None:
        conversation = [
            assistant.message_out(m)
            for m in assistant.messages_of(db, ticket.shared_conversation_id)
        ]
        if ticket.user_id != principal.user_id and context is not None:
            audit.record(
                db,
                action="support_ticket.transcript_viewed",
                entity_type="support_ticket",
                entity_id=ticket.id,
                actor_id=principal.user_id,
                context=context,
            )
            db.commit()
    return TicketDetail(
        **base.model_dump(),
        body=ticket.body,
        replies=[
            ReplyOut(
                id=r.id,
                author_id=r.author_id,
                author_name=name,
                is_staff=r.is_staff,
                body=r.body,
                created_at=r.created_at,
            )
            for r, name in replies
        ],
        conversation=conversation,
    )


def create_ticket(
    db: Session, principal: Principal, payload: TicketCreate, *, context: RequestContext
) -> TicketDetail:
    active = db.scalar(
        select(func.count())
        .select_from(SupportTicket)
        .where(SupportTicket.user_id == principal.user_id, SupportTicket.status.in_(_ACTIVE))
    )
    if (active or 0) >= MAX_OPEN_TICKETS_PER_USER:
        raise TooManyOpenTicketsError(
            f"You already have {MAX_OPEN_TICKETS_PER_USER} open requests. "
            "Wait for a reply or close one first."
        )
    shared: uuid.UUID | None = None
    if payload.conversation_id is not None:
        conversation = assistant.owned_conversation(db, principal, payload.conversation_id)
        if payload.share_conversation:
            shared = conversation.id
    elif payload.share_conversation:
        raise BadRequestError("Nothing to share: no conversation was given")
    ticket = SupportTicket(
        user_id=principal.user_id,
        subject=payload.subject,
        body=payload.body,
        shared_conversation_id=shared,
    )
    db.add(ticket)
    db.flush()
    audit.record(
        db,
        action="support_ticket.created",
        entity_type="support_ticket",
        entity_id=ticket.id,
        actor_id=principal.user_id,
        context=context,
        changes={"conversation_shared": shared is not None},
    )
    for staff_id in _staff_ids(db):
        if staff_id != principal.user_id:
            _notify(db, staff_id, "A new support request needs an answer", ticket)
    db.commit()
    db.refresh(ticket)
    return _detail(db, principal, ticket, context=None)


def list_mine(
    db: Session, principal: Principal, params: PageParams, *, status: TicketStatus | None
) -> Page[TicketOut]:
    stmt = select(SupportTicket).where(SupportTicket.user_id == principal.user_id)
    if status is not None:
        stmt = stmt.where(SupportTicket.status == status)
    return _page(db, stmt, params, staff_view=False)


def list_all(
    db: Session,
    principal: Principal,
    params: PageParams,
    *,
    status: TicketStatus | None,
    assigned_to_me: bool,
    unassigned: bool,
    q: str | None,
) -> Page[TicketOut]:
    stmt = select(SupportTicket)
    if status is not None:
        stmt = stmt.where(SupportTicket.status == status)
    if assigned_to_me:
        stmt = stmt.where(SupportTicket.assignee_id == principal.user_id)
    if unassigned:
        stmt = stmt.where(SupportTicket.assignee_id.is_(None))
    pattern = contains_pattern(q) if q else None
    if pattern:
        stmt = stmt.where(SupportTicket.subject.ilike(pattern, escape=LIKE_ESCAPE))
    return _page(db, stmt, params, staff_view=True)


def _page(db: Session, stmt, params: PageParams, *, staff_view: bool) -> Page[TicketOut]:  # type: ignore[no-untyped-def]
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = list(
        db.scalars(
            stmt.order_by(SupportTicket.updated_at.desc(), SupportTicket.id)
            .limit(params.limit)
            .offset(params.offset)
        )
    )
    return Page.build(_out(db, rows, staff_view=staff_view), total, params)


def get_ticket(
    db: Session, principal: Principal, ticket_id: uuid.UUID, *, context: RequestContext
) -> TicketDetail:
    ticket = _load(db, principal, ticket_id)
    return _detail(db, principal, ticket, context=context)


def reply(
    db: Session,
    principal: Principal,
    ticket_id: uuid.UUID,
    payload: ReplyCreate,
    *,
    context: RequestContext,
) -> TicketDetail:
    ticket = _load(db, principal, ticket_id, lock=True)
    if ticket.status == TicketStatus.CLOSED:
        raise TicketClosedError("This request is closed. Open a new one if you still need help.")
    is_owner = ticket.user_id == principal.user_id
    is_staff = principal.has("support:manage") and not is_owner
    db.add(
        SupportTicketReply(
            ticket_id=ticket.id, author_id=principal.user_id, is_staff=is_staff, body=payload.body
        )
    )
    previous = ticket.status
    if is_staff:
        if ticket.status == TicketStatus.OPEN:
            ticket.status = TicketStatus.IN_PROGRESS
        if ticket.assignee_id is None:
            ticket.assignee_id = principal.user_id
        _notify(db, ticket.user_id, "Support replied to your request", ticket)
    else:
        if ticket.status == TicketStatus.RESOLVED:
            ticket.status = TicketStatus.OPEN
            ticket.resolved_at = None
        recipients = [ticket.assignee_id] if ticket.assignee_id else _staff_ids(db)
        for recipient in recipients:
            if recipient and recipient != principal.user_id:
                _notify(db, recipient, "A requester added a message", ticket)
    ticket.updated_at = _now()
    audit.record(
        db,
        action="support_ticket.replied",
        entity_type="support_ticket",
        entity_id=ticket.id,
        actor_id=principal.user_id,
        context=context,
        changes={"staff": is_staff, "status": {"from": previous.value, "to": ticket.status.value}},
    )
    db.commit()
    db.refresh(ticket)
    return _detail(db, principal, ticket, context=None)


def _set_status(ticket: SupportTicket, new: TicketStatus) -> None:
    if new == ticket.status:
        return
    if new not in TICKET_TRANSITIONS[ticket.status]:
        raise InvalidTicketTransitionError(
            f"A request cannot move from {ticket.status.value} to {new.value}"
        )
    ticket.status = new
    ticket.resolved_at = _now() if new == TicketStatus.RESOLVED else None


def update(
    db: Session,
    principal: Principal,
    ticket_id: uuid.UUID,
    payload: TicketUpdate,
    *,
    context: RequestContext,
) -> TicketDetail:
    ticket = _load(db, principal, ticket_id, lock=True)
    changes: dict[str, object] = {}
    if payload.status is not None and payload.status != ticket.status:
        old = ticket.status
        _set_status(ticket, payload.status)
        changes["status"] = {"from": old.value, "to": ticket.status.value}
        if ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
            _notify(
                db,
                ticket.user_id,
                "Your support request was marked " + ticket.status.value.replace("_", " "),
                ticket,
            )
    assignee: uuid.UUID | None = ticket.assignee_id
    if payload.assign_to_me:
        assignee = principal.user_id
    elif payload.assignee_id is not None:
        target = users.get_by_id(db, payload.assignee_id)
        if target is None or not target.is_active:
            raise NotFoundError("User not found")
        if "support:manage" not in users.permission_codes(db, target.id):
            raise ConflictError("That person cannot handle support requests")
        assignee = target.id
    elif payload.unassign:
        assignee = None
    if assignee != ticket.assignee_id:
        changes["assignee_id"] = {
            "from": str(ticket.assignee_id) if ticket.assignee_id else None,
            "to": str(assignee) if assignee else None,
        }
        ticket.assignee_id = assignee
        if assignee is not None and assignee != principal.user_id:
            _notify(db, assignee, "A support request was assigned to you", ticket)
    if changes:
        ticket.updated_at = _now()
        audit.record(
            db,
            action="support_ticket.updated",
            entity_type="support_ticket",
            entity_id=ticket.id,
            actor_id=principal.user_id,
            context=context,
            changes=changes,
        )
        db.commit()
        db.refresh(ticket)
    return _detail(db, principal, ticket, context=None)


def close_own(
    db: Session, principal: Principal, ticket_id: uuid.UUID, *, context: RequestContext
) -> TicketDetail:
    """The requester closes their own request (they no longer need an answer)."""
    ticket = _load(db, principal, ticket_id, lock=True)
    if ticket.user_id != principal.user_id:
        raise NotFoundError("Ticket not found")
    if ticket.status == TicketStatus.CLOSED:
        return _detail(db, principal, ticket, context=None)
    _set_status(ticket, TicketStatus.CLOSED)
    ticket.updated_at = _now()
    audit.record(
        db,
        action="support_ticket.closed_by_requester",
        entity_type="support_ticket",
        entity_id=ticket.id,
        actor_id=principal.user_id,
        context=context,
    )
    db.commit()
    db.refresh(ticket)
    return _detail(db, principal, ticket, context=None)
