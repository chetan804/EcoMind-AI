"""Vocabulary and tuning values of the support module (help assistant, knowledge base, tickets)."""

from __future__ import annotations

from enum import StrEnum


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


# A ticket moves along these edges only. ``closed`` is terminal; a person who replies to a
# ``resolved`` ticket reopens it (see tickets.py).
TICKET_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.OPEN: frozenset(
        {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED}
    ),
    TicketStatus.IN_PROGRESS: frozenset(
        {TicketStatus.OPEN, TicketStatus.RESOLVED, TicketStatus.CLOSED}
    ),
    TicketStatus.RESOLVED: frozenset({TicketStatus.OPEN, TicketStatus.CLOSED}),
    TicketStatus.CLOSED: frozenset(),
}


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageKind(StrEnum):
    """How an assistant reply was produced. Shown to the person, never hidden."""

    QUESTION = "question"  # a person's own message
    KNOWLEDGE = "knowledge"  # quoted from knowledge-base articles or the sorting guide
    ACCOUNT_DATA = "account_data"  # read from the person's own records
    NO_ANSWER = "no_answer"  # nothing trustworthy was found; a ticket is offered
    NOT_PERMITTED = "not_permitted"  # the person's role cannot see that data


class SourceKind(StrEnum):
    ARTICLE = "article"
    SORTING_GUIDANCE = "sorting_guidance"
    ACCOUNT = "account"


# -- retrieval tuning ------------------------------------------------------------------------
# An answer is given only when at least this share of the question's meaningful words (after
# stemming and stop-word removal) occur in the article. Evaluated by
# ``tests/api/test_support_assistant_quality.py`` against a labelled question set.
MIN_QUERY_COVERAGE = 0.6
MAX_SOURCES = 2
# Below the answer threshold a source is only *suggested* ("possibly related"), never quoted.
MIN_RELATED_COVERAGE = 0.25
MAX_RELATED = 3
MAX_MESSAGE_LENGTH = 1000
MAX_ANSWER_CHARS = 900

# -- abuse limits ----------------------------------------------------------------------------
MAX_ASSISTANT_MESSAGES_PER_WINDOW = 30
ASSISTANT_WINDOW_MINUTES = 10
MAX_OPEN_TICKETS_PER_USER = 10
