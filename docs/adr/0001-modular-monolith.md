# ADR-0001: Modular monolith over microservices

**Status:** Accepted · **Date:** 2026-09

## Context

The platform spans auth/tenancy, citizen reporting, complaints, collection ops,
fleet, routing optimization, IoT ingestion, AI, sustainability accounting and
analytics. A common instinct is to split these into microservices from day one.

## Decision

Build a **single FastAPI application** with strictly domain-partitioned modules
(`app/<domain>/{models,router,service,schemas}.py`), one PostgreSQL database, and an
embedded job worker. Domain modules interact only through service functions — never
by importing each other's models directly where avoidable.

## Rationale

- **No committed scale problem exists yet.** Municipal workloads are thousands of
  events/day, not millions/sec. A monolith removes distributed-transactions,
  service-mesh and deployment-ordering complexity that microservices would add today.
- **Tenant isolation is easier to guarantee in one process** with one enforcement
  pattern (ADR-0002) than across services with independent query paths.
- **The exit door stays open.** Domain boundaries, per-domain services and a
  PostgreSQL-backed queue mean any module can be extracted later without rewrite.

## Consequences

- One deployable; operational simplicity (single healthcheck, single log stream).
- Team discipline required: keep domains decoupled (enforced in review).
- Horizontal scaling is per-process; the job worker can be split by config.
