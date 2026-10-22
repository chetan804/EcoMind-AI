# Help assistant and support desk (`support`)

A retrieval-only help assistant, the help-article knowledge base, and support requests (tickets) with replies. Design record: [ADR-0003](../../../../docs/decisions/ADR-0003-retrieval-help-assistant.md); quality evidence and limits: [docs/ml/support-assistant.md](../../../../docs/ml/support-assistant.md).

**Status:** implemented (migration `0015`). The assistant does **not** generate text: every reply is quoted from a published article, from the sorting guide, or read from the caller's own records, and it hands off to a support request when it has no answer.

## Ownership
- **Tables owned:** `knowledge_articles`, `assistant_conversations`, `assistant_messages`, `support_tickets`, `support_ticket_replies`
- **Files:** `models.py`, `constants.py`, `schemas.py`, `router.py`, `retrieval.py` (PostgreSQL full-text search), `intents.py`, `assistant.py`, `knowledge.py`, `tickets.py`, and `knowledge/platform_help.json` (31 starter articles).

## API
`/api/v1/support/...` (articles, assistant messages and feedback, tickets). Permissions `support:ask`, `support:manage`, `knowledge:manage`; see the generated [route matrix](../../../../docs/security/route-permission-matrix.md) and [docs/api/support-api.md](../../../../docs/api/support-api.md).

## Operations
`python -m app.cli seed-support-knowledge` loads or updates the starter articles; `purge-assistant-conversations` removes conversations past `ASSISTANT_RETENTION_DAYS`. Neither runs by itself: the operator schedules them.

## Tests
`tests/api/test_support.py`, `tests/api/test_support_assistant_quality.py` (held-out questions), `tests/e2e/specs/support.spec.ts`.
Run: `make test-backend`.
