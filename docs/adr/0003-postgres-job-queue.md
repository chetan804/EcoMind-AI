# ADR-0003: PostgreSQL-backed job queue (no Redis/broker dependency)

**Status:** Accepted · **Date:** 2026-09

## Context

Route optimization, AI batch work, SLA escalation sweeps and sustainability
recompute should run off the request path. Classic answers add Redis, RabbitMQ or
Celery — extra infrastructure, extra failure modes.

## Decision

Jobs are rows in the `jobs` table; workers claim them with
`SELECT … FOR UPDATE SKIP LOCKED`. An asyncio worker loop is embedded in the API
process by default (`ECOMIND_RUN_EMBEDDED_WORKER`) and can be split into dedicated
instances. Jobs carry status, attempts, backoff and a dead-letter terminal state.

## Rationale

- The database is already the source of truth and the transaction coordinator —
  enqueuing a job in the same transaction as the state change that triggered it
  removes dual-write inconsistency.
- `SKIP LOCKED` gives safe multi-worker claiming without a broker.
- One fewer service to deploy, secure, monitor and back up for small/medium
  operators (the primary customer shape).

## Consequences

- Queue throughput is bounded by Postgres (fine at this scale; revisit with a broker
  if job volume exceeds ~10⁴/min sustained).
- Operational visibility is SQL (`SELECT status, count(*) FROM jobs …`).
- Redis remains an optional dependency only for shared rate limiting (ADR-0008).
