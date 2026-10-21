"""Request and response bodies of the support module."""

from __future__ import annotations

import datetime as dt
import re
import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.support.constants import (
    MAX_MESSAGE_LENGTH,
    MessageKind,
    MessageRole,
    SourceKind,
    TicketStatus,
)

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _clean(value: str) -> str:
    # The assistant and the ticket desk store plain text; control characters are never useful.
    return "".join(ch for ch in value if ch in "\n\t" or ch.isprintable()).strip()


# -- knowledge base ------------------------------------------------------------------------------
class ArticleBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=20, max_length=8000)
    category: str = Field(min_length=2, max_length=60)
    source: str = Field(
        min_length=3,
        max_length=200,
        description="Where the content comes from (document, policy, owner).",
    )
    keywords: str = Field(
        default="",
        max_length=500,
        description="Other words people use for this topic (synonyms); searched, not shown.",
    )
    published: bool = True


class ArticleCreate(ArticleBase):
    slug: str = Field(min_length=3, max_length=100)

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, value: str) -> str:
        if not _SLUG.fullmatch(value):
            raise ValueError("Use lowercase letters, digits and single hyphens")
        return value


class ArticleUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=3, max_length=200)
    body: str | None = Field(default=None, min_length=20, max_length=8000)
    category: str | None = Field(default=None, min_length=2, max_length=60)
    source: str | None = Field(default=None, min_length=3, max_length=200)
    keywords: str | None = Field(default=None, max_length=500)
    published: bool | None = None


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    body: str
    category: str
    keywords: str
    source: str
    published: bool
    updated_at: dt.datetime


# -- assistant -----------------------------------------------------------------------------------
class AskRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)

    @field_validator("message")
    @classmethod
    def _printable(cls, value: str) -> str:
        cleaned = _clean(value)
        if not cleaned:
            raise ValueError("The message is empty")
        return cleaned


class SourceOut(BaseModel):
    kind: SourceKind
    id: uuid.UUID | None = None
    title: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: MessageRole
    kind: MessageKind
    content: str
    sources: list[SourceOut]
    helpful: bool | None
    created_at: dt.datetime


class AskResponse(BaseModel):
    conversation_id: uuid.UUID
    question: MessageOut
    reply: MessageOut
    suggest_ticket: bool = Field(
        description="True when the assistant could not answer and a person should be asked."
    )


class ConversationOut(BaseModel):
    id: uuid.UUID
    messages: list[MessageOut]


class FeedbackRequest(BaseModel):
    helpful: bool


class AssistantStats(BaseModel):
    since: dt.datetime
    questions: int
    answered_from_knowledge: int
    answered_from_account: int
    no_answer: int
    not_permitted: int
    rated: int
    rated_helpful: int


# -- tickets -------------------------------------------------------------------------------------
class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=10, max_length=4000)
    conversation_id: uuid.UUID | None = None
    share_conversation: bool = False

    @field_validator("subject", "body")
    @classmethod
    def _printable(cls, value: str) -> str:
        cleaned = _clean(value)
        if not cleaned:
            raise ValueError("The text is empty")
        return cleaned


class ReplyCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)

    @field_validator("body")
    @classmethod
    def _printable(cls, value: str) -> str:
        cleaned = _clean(value)
        if not cleaned:
            raise ValueError("The reply is empty")
        return cleaned


class TicketUpdate(BaseModel):
    status: TicketStatus | None = None
    assignee_id: uuid.UUID | None = None
    assign_to_me: bool = False
    unassign: bool = False


class ReplyOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str
    is_staff: bool
    body: str
    created_at: dt.datetime


class TicketOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    requester_name: str | None = Field(default=None, description="Shown to support staff only.")
    subject: str
    status: TicketStatus
    assignee_id: uuid.UUID | None
    assignee_name: str | None
    reply_count: int
    conversation_shared: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    resolved_at: dt.datetime | None


class TicketDetail(TicketOut):
    body: str
    replies: list[ReplyOut]
    conversation: list[MessageOut] | None = Field(
        default=None, description="Present only when the requester chose to share it."
    )
