# ADR-0008: Infrastructure simplicity — in-process rate limiter, local-first storage

**Status:** Accepted (with explicit revisit triggers) · **Date:** 2026-09

## Context

Two cross-cutting infra concerns usually drag in dependencies: rate limiting
(Redis) and file storage (S3). The target customer profile (municipalities,
campuses, small operators) deploys one box if possible.

## Decision

- **Rate limiting**: in-process, token-bucket style, differentiated by category
  (auth 15/min … telemetry 600/min) keyed on client IP. Correct and safe for one
  process or a few replicas behind a consistent LB hash; documented limit.
- **Object storage**: a `Storage` abstraction (`app/core/storage.py`) with the
  local-filesystem backend implemented; S3-compatible backends plug in at the seam.
  Files are checksummed, MIME-allow-listed and stored outside the web root.
- Both choices have **explicit revisit triggers**: multi-replica scaling → shared
  limiter (Redis) or LB-level rate limiting; storage growth / multi-region → S3
  backend.

## Rationale

- Every added service multiplies deployment failure modes; neither concern needs
  a distributed system at current scale.
- Abstractions keep the swap cheap — the limiter is one module, storage is one
  interface.

## Consequences

- Single-container deployments work with zero external services beyond Postgres.
- Known limitation documented (KNOWN_LIMITATIONS.md) — do not scale to many
  replicas without replacing the limiter.
