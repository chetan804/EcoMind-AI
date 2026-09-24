# ADR-0004: Provider-independent AI with a labelled deterministic baseline

**Status:** Accepted · **Date:** 2026-09

## Context

Requirements: AI-assisted classification with structured outputs, schema/range/
confidence validation, a human-review path, defense against prompt injection — and
a hard rule: **never fabricate AI results**. The platform must also demo well with
no API keys configured, without pretending simulated output is real.

## Decision

- Define a `Provider` interface (`classify_report`, structured output contract);
  register OpenAI, Anthropic and Google implementations behind env configuration.
  **No model names are hard-coded** — provider + model are deployment config.
- Always include a **deterministic heuristic provider** (keyword/rule based).
  Its inferences are written with `is_simulated=true` and shown with a SIMULATED
  badge; they still pass the same validation pipeline.
- Validate every inference: category must exist in the org's category list,
  confidence ∈ [0,1]; below the acceptance threshold the item is routed to human
  review rather than auto-accepted.
- Treat citizen text as **data, never instructions** (injection defense-in-depth).

## Rationale

- Provider independence prevents lock-in and keeps procurement flexible.
- A labelled baseline means every environment has a working, honest AI path —
  demos run without keys, and "simulated" is a database flag, not marketing copy.
- Human review for low confidence is cheaper than wrong auto-triage.

## Consequences

- Switching vendors is a config change; adding one is a small adapter class.
- The UI must always render the simulation badge and confidence — enforced in the
  design system (`SimBadge`).
