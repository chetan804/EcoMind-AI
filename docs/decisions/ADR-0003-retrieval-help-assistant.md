# ADR-0003: The help assistant answers by retrieval, not by a generative model

- **Status:** Accepted
- **Date:** 2026-10-21

## Context
The product needs an assistant that helps people use the platform and solve customer queries. The owner did not choose a language-model provider, and no provider key, network route or data-processing agreement exists in this project. The assistant will be asked about waste handling, accounts and rewards, where a confident wrong answer costs trust (or safety, for hazardous waste), and conversations can contain personal data.

## Decision
1. Replies are **quoted** from curated sources: published help articles (`knowledge_articles`) and the sorting guide, found with PostgreSQL full-text search over title, body and curated keywords. An answer needs an *anchored* match (a matched word in the title or keywords) and at least 60% of the question's meaningful words in one article.
2. Questions about the person's **own** data (points, reports, support requests) are answered by a few narrow patterns that read the database through the same permission checks as the rest of the API.
3. When nothing qualifies the assistant **says it does not know**, lists up to three possibly related articles as suggestions (never as the answer) and offers to send the question to a person (a support request, with the chat shared only if the person ticks a box).
4. Every reply states how it was produced and lists its sources. The UI says plainly that the assistant does not write free-form answers.
5. No conversation text leaves the platform. No external service is called.

## Why this and not an LLM now
- **Cannot hallucinate:** the worst failure is silence, which the UI turns into a hand-off to a person. A generative model would also need retrieval, evaluation and guardrails to be safe here, so retrieval has to be built anyway.
- **Privacy and cost:** nothing is sent to a third party; no key, quota or per-message fee.
- **Testable offline:** the quality gate (`backend/tests/api/test_support_assistant_quality.py`) and the whole feature run in CI with only PostgreSQL.
- **Honest limit:** it misses questions worded unlike the articles (see `docs/ml/support-assistant.md`: about half of an author-written held-out set got no direct answer). Curated keywords and the related-article list reduce this; they do not remove it.

## Extension point
`retrieval.find_answers` returns ranked, sourced passages. A generative layer could be added later that may only rephrase those passages and must cite them, behind a new setting that is off by default, with the same quality gate extended to check faithfulness. That needs an owner decision on provider, data processing and cost, and a new ADR. Embedding-based search is a lower-risk alternative to try first; it would need a licence-clean model and the same held-out evaluation.

## Alternatives rejected
- **Hosted LLM with the knowledge base in the prompt:** no provider, key or data agreement; unbounded cost; harder to test; answers cannot be guaranteed to come from the sources.
- **Self-hosted open-weight LLM:** model weights, GPU or heavy CPU and licence review are out of scope for the locked, modular-monolith deployment.
- **Rule-based chat flows only:** brittle and still needs the knowledge base.

## Consequences
- A new module `support` (tables in migration 0015, permissions `support:ask`, `support:manage`, `knowledge:manage`), no new service.
- Quality depends on the articles staff maintain; the staff screen shows which questions went unanswered (counts only, no text).
