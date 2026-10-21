"""Support endpoints, mounted at ``/api/v1/support``: help articles, the assistant and tickets."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import DbSession
from app.common.pagination import Page, PageParams, page_params
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal, require_permissions
from app.modules.support import assistant, knowledge, tickets
from app.modules.support.constants import TicketStatus
from app.modules.support.schemas import (
    ArticleCreate,
    ArticleOut,
    ArticleUpdate,
    AskRequest,
    AskResponse,
    AssistantStats,
    ConversationOut,
    FeedbackRequest,
    MessageOut,
    ReplyCreate,
    TicketCreate,
    TicketDetail,
    TicketOut,
    TicketUpdate,
)

router = APIRouter()

CanAsk = Annotated[Principal, Depends(require_permissions("support:ask"))]
CanManageSupport = Annotated[Principal, Depends(require_permissions("support:manage"))]
CanManageKnowledge = Annotated[Principal, Depends(require_permissions("knowledge:manage"))]
Pagination = Annotated[PageParams, Depends(page_params)]


def _ctx(request: Request) -> RequestContext:
    return RequestContext.from_request(request)


# -- help articles -------------------------------------------------------------------------------
@router.get("/articles", response_model=Page[ArticleOut])
def list_articles(
    db: DbSession,
    principal: CanAsk,
    params: Pagination,
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=60)] = None,
    include_unpublished: bool = False,
) -> Page[ArticleOut]:
    """`include_unpublished` is honoured only for people who can manage articles."""
    return knowledge.list_articles(
        db, principal, params, q=q, category=category, include_unpublished=include_unpublished
    )


@router.get("/articles/categories", response_model=list[str])
def list_categories(db: DbSession, principal: CanAsk) -> list[str]:
    return knowledge.categories(db, principal)


@router.get("/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: uuid.UUID, db: DbSession, principal: CanAsk) -> ArticleOut:
    return knowledge.get_article(db, principal, article_id)


@router.post("/articles", response_model=ArticleOut, status_code=status.HTTP_201_CREATED)
def create_article(
    payload: ArticleCreate, request: Request, db: DbSession, principal: CanManageKnowledge
) -> ArticleOut:
    return knowledge.create_article(db, principal, payload, context=_ctx(request))


@router.patch("/articles/{article_id}", response_model=ArticleOut)
def update_article(
    article_id: uuid.UUID,
    payload: ArticleUpdate,
    request: Request,
    db: DbSession,
    principal: CanManageKnowledge,
) -> ArticleOut:
    return knowledge.update_article(db, principal, article_id, payload, context=_ctx(request))


# -- assistant -----------------------------------------------------------------------------------
@router.post("/assistant/messages", response_model=AskResponse)
def ask(payload: AskRequest, request: Request, db: DbSession, principal: CanAsk) -> AskResponse:
    """Ask one question. The reply quotes its sources or says it does not know; it never guesses."""
    return assistant.ask(db, principal, payload, context=_ctx(request))


@router.get("/assistant/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: uuid.UUID, db: DbSession, principal: CanAsk
) -> ConversationOut:
    return assistant.get_conversation(db, principal, conversation_id)


@router.post("/assistant/messages/{message_id}/feedback", response_model=MessageOut)
def give_feedback(
    message_id: uuid.UUID, payload: FeedbackRequest, db: DbSession, principal: CanAsk
) -> MessageOut:
    return assistant.give_feedback(db, principal, message_id, helpful=payload.helpful)


@router.get("/assistant/stats", response_model=AssistantStats)
def assistant_stats(
    db: DbSession,
    principal: CanManageSupport,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> AssistantStats:
    return assistant.stats(db, days=days)


# -- tickets -------------------------------------------------------------------------------------
@router.post("/tickets", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate, request: Request, db: DbSession, principal: CanAsk
) -> TicketDetail:
    return tickets.create_ticket(db, principal, payload, context=_ctx(request))


@router.get("/tickets/mine", response_model=Page[TicketOut])
def my_tickets(
    db: DbSession,
    principal: CanAsk,
    params: Pagination,
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
) -> Page[TicketOut]:
    return tickets.list_mine(db, principal, params, status=status_filter)


@router.get("/tickets", response_model=Page[TicketOut])
def all_tickets(
    db: DbSession,
    principal: CanManageSupport,
    params: Pagination,
    status_filter: Annotated[TicketStatus | None, Query(alias="status")] = None,
    assigned_to_me: bool = False,
    unassigned: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> Page[TicketOut]:
    return tickets.list_all(
        db,
        principal,
        params,
        status=status_filter,
        assigned_to_me=assigned_to_me,
        unassigned=unassigned,
        q=q,
    )


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
def get_ticket(
    ticket_id: uuid.UUID, request: Request, db: DbSession, principal: CanAsk
) -> TicketDetail:
    return tickets.get_ticket(db, principal, ticket_id, context=_ctx(request))


@router.post("/tickets/{ticket_id}/replies", response_model=TicketDetail)
def reply_to_ticket(
    ticket_id: uuid.UUID,
    payload: ReplyCreate,
    request: Request,
    db: DbSession,
    principal: CanAsk,
) -> TicketDetail:
    return tickets.reply(db, principal, ticket_id, payload, context=_ctx(request))


@router.patch("/tickets/{ticket_id}", response_model=TicketDetail)
def update_ticket(
    ticket_id: uuid.UUID,
    payload: TicketUpdate,
    request: Request,
    db: DbSession,
    principal: CanManageSupport,
) -> TicketDetail:
    return tickets.update(db, principal, ticket_id, payload, context=_ctx(request))


@router.post("/tickets/{ticket_id}/close", response_model=TicketDetail)
def close_ticket(
    ticket_id: uuid.UUID, request: Request, db: DbSession, principal: CanAsk
) -> TicketDetail:
    return tickets.close_own(db, principal, ticket_id, context=_ctx(request))
