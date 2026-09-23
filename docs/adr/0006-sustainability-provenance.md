# ADR-0006: Sustainability engine — versioned factors, quality labels, no carbon credits

**Status:** Accepted · **Date:** 2026-09

## Context

Environmental accounting is rife with greenwashing. Requirements: configurable
versioned emission factors, a documented methodology, and a hard distinction
between measured, estimated and modeled data. The consumer UI must not present
tradable "carbon credits".

## Decision

- **Platform-level factor library**: each factor has code, version, unit, value,
  source and year (e.g. EPA WARM). Treatments reference factor code + version —
  historical records stay reproducible after factor updates.
- **Carbon records with provenance**: every computed record stores scope, activity
  value + unit, co2e, `quality ∈ {measured, estimated, modeled}`, factor
  code/version, methodology text and assumptions JSON.
- **Avoided emissions are a separate `scope=avoided` record** — a modeled
  counterfactual ("what if diverted waste had gone to landfill"), never summed
  into net emissions, always labelled.
- **Citizen rewards are recognition points only.** No tokens, no credits, no
  market instruments anywhere in the product.

## Rationale

- Versioned factors make numbers auditable and comparable across reporting periods.
- Quality labels let analysts cite figures honestly (council reports, ESG filings).
- Merging modeled avoidance into net totals is the single most common
  greenwashing pattern; separating the scopes makes it structurally impossible
  here.
- Points-not-credits avoids regulatory exposure and keeps the incentive
  pro-social.

## Consequences

- The sustainability UI shows a records ledger and factor library, not just
  headline numbers.
- Analysts can defend every figure back to a factor version and methodology string.
