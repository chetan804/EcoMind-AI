"""The help assistant: one question in, one sourced reply out. Each public function commits."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, TooManyRequestsError
from app.modules.audit import service as audit
from app.modules.audit.service import RequestContext
from app.modules.auth.dependencies import Principal
from app.modules.support import intents, retrieval
from app.modules.support.constants import (
    ASSISTANT_WINDOW_MINUTES,
    MAX_ASSISTANT_MESSAGES_PER_WINDOW,
    MessageKind,
    MessageRole,
    SourceKind,
)
from app.modules.support.models import (
    AssistantConversation,
    AssistantMessage,
    SupportTicket,
)
from app.modules.support.schemas import (
    AskRequest,
    AskResponse,
    AssistantStats,
    ConversationOut,
    MessageOut,
    SourceOut,
)

NO_ANSWER = (
    "I could not find a reliable answer to that in the help articles or the sorting guide, "
    "and I would rather not guess. You can rephrase the question, read the related articles "
    "below if any are listed, or send it to the support team and a person will reply."
)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def message_out(message: AssistantMessage) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        kind=message.kind,
        content=message.content,
        sources=[SourceOut.model_validate(s) for s in message.sources],
        helpful=message.helpful,
        created_at=message.created_at,
    )


def owned_conversation(
    db: Session, principal: Principal, conversation_id: uuid.UUID
) -> AssistantConversation:
    conversation = db.get(AssistantConversation, conversation_id)
    # Somebody else's conversation looks exactly like a missing one.
    if conversation is None or conversation.user_id != principal.user_id:
        raise NotFoundError("Conversation not found")
    return conversation


def _enforce_rate_limit(db: Session, principal: Principal, now: dt.datetime) -> None:
    window = dt.timedelta(minutes=ASSISTANT_WINDOW_MINUTES)
    times = list(
        db.scalars(
            select(AssistantMessage.created_at)
            .join(
                AssistantConversation,
                AssistantConversation.id == AssistantMessage.conversation_id,
            )
            .where(
                AssistantConversation.user_id == principal.user_id,
                AssistantMessage.role == MessageRole.USER,
                AssistantMessage.created_at > now - window,
            )
            .order_by(AssistantMessage.created_at)
        )
    )
    if len(times) >= MAX_ASSISTANT_MESSAGES_PER_WINDOW:
        wait = max(1, int((times[0] + window - now).total_seconds()) + 1)
        raise TooManyRequestsError(
            "You are asking very quickly. Please wait a moment.",
            headers={"Retry-After": str(wait)},
        )


def ask(
    db: Session, principal: Principal, payload: AskRequest, *, context: RequestContext
) -> AskResponse:
    now = _now()
    _enforce_rate_limit(db, principal, now)
    if payload.conversation_id is None:
        conversation = AssistantConversation(user_id=principal.user_id)
        db.add(conversation)
        db.flush()
        audit.record(
            db,
            action="assistant.conversation_started",
            entity_type="assistant_conversation",
            entity_id=conversation.id,
            actor_id=principal.user_id,
            context=context,
        )
    else:
        conversation = owned_conversation(db, principal, payload.conversation_id)

    question = AssistantMessage(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        kind=MessageKind.QUESTION,
        content=payload.message,
        sources=[],
    )
    db.add(question)
    db.flush()

    kind: MessageKind
    sources: list[dict[str, object]]
    account = intents.answer_about_account(db, principal, payload.message)
    if isinstance(account, intents.AccountAnswer):
        kind, content = MessageKind.ACCOUNT_DATA, account.content
        sources = [{"kind": SourceKind.ACCOUNT.value, "id": None, "title": account.source_title}]
        audit.record(
            db,
            action="assistant.account_data_read",
            entity_type="assistant_conversation",
            entity_id=conversation.id,
            actor_id=principal.user_id,
            context=context,
            changes={"intent": account.intent},
        )
    elif isinstance(account, intents.Refusal):
        kind, content, sources = MessageKind.NOT_PERMITTED, account.content, []
    else:
        hits, answer = retrieval.find_answers(db, payload.message)
        if answer is None:
            # Near misses are offered as links to read, clearly not as the answer.
            related = retrieval.find_related(db, payload.message)
            kind, content = MessageKind.NO_ANSWER, NO_ANSWER
            sources = [{"kind": h.kind.value, "id": str(h.id), "title": h.title} for h in related]
        else:
            kind, content = MessageKind.KNOWLEDGE, answer
            sources = [{"kind": h.kind.value, "id": str(h.id), "title": h.title} for h in hits]

    reply = AssistantMessage(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        kind=kind,
        content=content,
        sources=sources,
    )
    db.add(reply)
    conversation.updated_at = now
    db.commit()
    db.refresh(question)
    db.refresh(reply)
    return AskResponse(
        conversation_id=conversation.id,
        question=message_out(question),
        reply=message_out(reply),
        suggest_ticket=kind in {MessageKind.NO_ANSWER, MessageKind.NOT_PERMITTED},
    )


def messages_of(db: Session, conversation_id: uuid.UUID) -> list[AssistantMessage]:
    return list(
        db.scalars(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversation_id)
            .order_by(
                AssistantMessage.created_at, AssistantMessage.role.desc(), AssistantMessage.id
            )
        )
    )


def get_conversation(
    db: Session, principal: Principal, conversation_id: uuid.UUID
) -> ConversationOut:
    conversation = owned_conversation(db, principal, conversation_id)
    return ConversationOut(
        id=conversation.id, messages=[message_out(m) for m in messages_of(db, conversation.id)]
    )


def give_feedback(
    db: Session, principal: Principal, message_id: uuid.UUID, *, helpful: bool
) -> MessageOut:
    message = db.get(AssistantMessage, message_id)
    if message is None:
        raise NotFoundError("Message not found")
    conversation = db.get(AssistantConversation, message.conversation_id)
    if (
        conversation is None
        or conversation.user_id != principal.user_id
        or message.role != MessageRole.ASSISTANT
    ):
        raise NotFoundError("Message not found")
    message.helpful = helpful
    db.commit()
    db.refresh(message)
    return message_out(message)


def stats(db: Session, *, days: int) -> AssistantStats:
    since = _now() - dt.timedelta(days=days)
    rows = db.execute(
        select(
            AssistantMessage.kind,
            func.count(),
            func.count(AssistantMessage.helpful),
            func.count().filter(AssistantMessage.helpful.is_(True)),
        )
        .where(AssistantMessage.created_at >= since)
        .group_by(AssistantMessage.kind)
    ).all()
    by_kind = {kind: (int(n), int(rated), int(helpful)) for kind, n, rated, helpful in rows}

    def count(kind: MessageKind) -> int:
        return by_kind.get(kind, (0, 0, 0))[0]

    return AssistantStats(
        since=since,
        questions=count(MessageKind.QUESTION),
        answered_from_knowledge=count(MessageKind.KNOWLEDGE),
        answered_from_account=count(MessageKind.ACCOUNT_DATA),
        no_answer=count(MessageKind.NO_ANSWER),
        not_permitted=count(MessageKind.NOT_PERMITTED),
        rated=sum(v[1] for v in by_kind.values()),
        rated_helpful=sum(v[2] for v in by_kind.values()),
    )


def purge_old_conversations(db: Session, *, older_than_days: int) -> int:
    """Delete transcripts idle for that long, except those a person shared with a ticket."""
    cutoff = _now() - dt.timedelta(days=older_than_days)
    shared = select(SupportTicket.shared_conversation_id).where(
        SupportTicket.shared_conversation_id.is_not(None)
    )
    result = db.execute(
        delete(AssistantConversation).where(
            AssistantConversation.updated_at < cutoff,
            AssistantConversation.id.not_in(shared),
        )
    )
    db.commit()
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
