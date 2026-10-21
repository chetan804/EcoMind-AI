# Support API: help assistant, help articles, support requests

Base path `/api/v1/support`. Design rationale: `docs/decisions/ADR-0003-retrieval-help-assistant.md`. Quality evidence: `docs/ml/support-assistant.md`.

Permissions: `support:ask` (citizen, collector, facility operator, manager, administrator), `support:manage` and `knowledge:manage` (manager, administrator). The assistant is **not** a language model; every reply is quoted from a published help article, from the sorting guide, or read from the caller's own records.

## Help articles

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /articles` | `support:ask` | Published articles (`q`, `category`, page). `include_unpublished=true` is honoured only for `knowledge:manage` |
| `GET /articles/categories` | `support:ask` | Category names |
| `GET /articles/{id}` | `support:ask` | One article (unpublished: `404` for people who cannot manage) |
| `POST /articles` | `knowledge:manage` | Create (`201`); `slug` is lowercase words joined by hyphens, unique, immutable |
| `PATCH /articles/{id}` | `knowledge:manage` | Edit text, category, source, `keywords`, `published` |

Every article carries a `source` (where the content comes from) and optional `keywords` (synonyms that are searched, never shown). Both are included in the search index (migration 0015). Starter articles: `python -m app.cli seed-support-knowledge` (idempotent; articles already edited in the application are left alone).

## Assistant

| Method and path | Permission | Purpose |
|---|---|---|
| `POST /assistant/messages` | `support:ask` | `{message, conversation_id?}` returns `{conversation_id, question, reply, suggest_ticket}` |
| `GET /assistant/conversations/{id}` | `support:ask` | Own conversation only (`404` for anyone else's) |
| `POST /assistant/messages/{id}/feedback` | `support:ask` | `{helpful: bool}` on one of own assistant replies |
| `GET /assistant/stats?days=30` | `support:manage` | Counts of questions, answers by kind, ratings (no message text) |

`reply.kind` says how the reply was produced and is always shown to the person:

| `kind` | Meaning | `sources` |
|---|---|---|
| `knowledge` | Quoted from up to 2 articles or sorting-guide entries | the quoted ones |
| `account_data` | Read from the caller's own points, waste reports or support requests at the moment of asking | `[{kind: account}]` |
| `no_answer` | Nothing matched well enough; the assistant says it does not know | up to 3 *possibly related* articles, never quoted |
| `not_permitted` | The question is about data the caller's role cannot see | none |

Rules: messages are 1 to 1000 printable characters; a person may send 30 messages per 10 minutes (`429`); a conversation belongs to its creator. Replies are plain text. Audit events: `assistant.conversation_started`, `assistant.account_data_read`, `knowledge_article.created`, `knowledge_article.updated`. Conversations idle for `ASSISTANT_RETENTION_DAYS` (default 90) are removed by `python -m app.cli purge-assistant-conversations`, except those a person attached to a support request.

## Support requests

| Method and path | Permission | Purpose |
|---|---|---|
| `POST /tickets` | `support:ask` | `{subject, body, conversation_id?, share_conversation}` (`201`); at most 10 open per person (`409 too_many_open_tickets`) |
| `GET /tickets/mine` | `support:ask` | Own requests (`status`) |
| `GET /tickets` | `support:manage` | Queue (`status`, `assigned_to_me`, `unassigned`, `q`) |
| `GET /tickets/{id}` | `support:ask` | Own request, or any for staff; replies, and the chat only if shared |
| `POST /tickets/{id}/replies` | `support:ask` | Reply (requester or staff). A reply to a resolved request reopens it |
| `PATCH /tickets/{id}` | `support:manage` | `status`, `assign_to_me`, `unassign` |
| `POST /tickets/{id}/close` | `support:ask` | The requester closes their own request |

Statuses and edges: `open` to `in_progress`, `resolved` or `closed`; `in_progress` to `open`, `resolved` or `closed`; `resolved` to `open` or `closed`; `closed` is final (`409 invalid_ticket_transition`, `409 ticket_closed`). Only a person holding `support:manage` can be assigned.

Privacy: the assistant conversation is attached only when the requester sets `share_conversation` (default false). When staff open a ticket with a shared chat, `support_ticket.transcript_viewed` is audited. Staff are notified of new requests and requesters' messages; requesters when staff reply. Audit events: `support_ticket.created`, `.replied`, `.updated`, `.closed_by_requester`, `.transcript_viewed`.
