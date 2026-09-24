# Architecture Decision Records

ADRs capture *why* EcoMind-AI is built the way it is — including places where we
deliberately chose a different path than a naive reading of the requirements.

| ADR | Decision |
| --- | --- |
| [0001](0001-modular-monolith.md) | Modular monolith over microservices |
| [0002](0002-tenant-isolation-strategy.md) | Shared-schema tenant scoping enforced in the repository layer + release-blocking tests |
| [0003](0003-postgres-job-queue.md) | PostgreSQL-backed job queue over Redis/Broker |
| [0004](0004-ai-provider-abstraction.md) | Provider-independent AI with a labelled deterministic baseline |
| [0005](0005-routing-two-layer.md) | Separate stop-sequencing (OR-Tools) from road geometry (OSRM) |
| [0006](0006-sustainability-provenance.md) | Versioned factors + quality labels; no tradable carbon credits |
| [0007](0007-spa-architecture.md) | Same-origin SPA: HashRouter + reverse proxy, relative API URLs |
| [0008](0008-infrastructure-simplicity.md) | In-process rate limiter & local-first storage with clean seams |
