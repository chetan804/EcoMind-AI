# ADR-0001: Modular monolith for the backend

- **Status:** Accepted
- **Date:** 2026-10-18

## Context
EcoMind AI spans 18 domains (reports, classification, collection, routing, facilities, fleet, circular economy, analytics, forecasting, anomalies, incidents, guidance, passports, rewards, notifications, audit, users/auth, administration). Many workflows cross domains and need transactional consistency (for example completing a collection event, recording recovery and awarding points). The team is small and the product is new; domain boundaries will still move as requirements become clear.

## Decision
One deployable FastAPI backend, internally divided into modules under `backend/app/modules/<name>/` with a fixed internal contract, one PostgreSQL database, and one Alembic migration history. Modules own their tables and expose behaviour to each other only through service interfaces. Shared infrastructure lives in `core/`, `db/`, `common/`. Dependency direction is documented and acyclic (`docs/architecture/component-boundaries.md`).

## Consequences
- Cross-module operations run in a single database transaction, with no distributed-transaction or eventual-consistency machinery.
- One deployment, one set of logs, simple local development and CI.
- Boundaries are enforced by convention, review and tests, not by the network. Discipline is required: no module writes another module's tables.
- Scaling is vertical/horizontal for the whole backend; individual domains cannot be scaled separately.
- ML training stays outside the backend process; inference is invoked in-process through the module's service.

## Alternatives considered
- **Microservice per feature:** rejected. Distributed transactions, per-service deployment and contract versioning cost far more than the current scale justifies; boundaries are not yet stable.
- **Single flat application (no modules):** rejected. Would blur ownership and make later extraction impossible.
- **Separate service only for ML:** deferred. Reconsider if model serving needs GPUs, different scaling or a different release cadence.

## Migration plan (if a module must become a service later)
1. The module already has its own tables and service interface; add an HTTP/queue adapter that implements the same interface.
2. Move its tables to a separate schema/database, replacing foreign keys to other modules by ids plus service calls.
3. Introduce infrastructure (broker, service-to-service auth) in its own ADR at that time.

## Review triggers
Measured scaling bottleneck in one domain; independent release cadence required by a team; a module needing a different runtime.
