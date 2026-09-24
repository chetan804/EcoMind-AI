# Architecture

## Overview

EcoMind-AI is a **modular monolith**: one deployable backend process with strictly
domain-partitioned code, plus a single-page frontend. This shape was chosen deliberately
(ADR-0001) — waste-management workloads fit one well-factored process, and the domain
boundaries leave a clean path to extract services later if scale demands it.

```
┌──────────────────────────────── Browser ────────────────────────────────┐
│  React 19 SPA (Vite, Tailwind v4, TanStack Query, Leaflet, Recharts)    │
│  relative /api/v1 URLs only — served same-origin (dev proxy / nginx)    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │ HTTPS (JSON, JWT bearer)
┌───────────────────────────────▼─────────────────────────────────────────┐
│                      FastAPI application (uvicorn)                      │
│  middleware: request-id + structured logging · rate limits · CORS       │
│  error handlers: structured JSON, no stack traces / secrets leaked      │
│                                                                         │
│  ┌── domains (app/*) ────────────────────────────────────────────────┐  │
│  │ auth · orgs · users · waste · complaints · collection · fleet     │  │
│  │ routing · iot · ai · media · sustainability · analytics           │  │
│  │ notifications · rewards · admin · audit · jobs · core             │  │
│  │          (each: models / router / service / schemas)              │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│  embedded worker loop (PG-backed job queue, configurable off)           │
└───────┬───────────────────────┬───────────────────────┬─────────────────┘
        │                       │                       │
┌───────▼────────┐   ┌──────────▼─────────┐   ┌─────────▼──────────┐
│ PostgreSQL 16  │   │ Local/S3 storage   │   │ External providers │
│ (single source │   │ (abstraction in    │   │ OSRM · LLM APIs    │
│  of truth)     │   │  core/storage.py)  │   │ (optional, keyed)  │
└────────────────┘   └────────────────────┘   └────────────────────┘
```

## Backend structure

Each domain module under `backend/app/<domain>/` contains:

- `models.py` — SQLAlchemy 2.0 declarative models (async ORM).
- `router.py` — FastAPI routes; thin, no business logic.
- `service.py` — business logic, pure functions over a session where possible.
- `schemas.py` — Pydantic v2 request/response contracts.

`core/` holds cross-cutting infrastructure: config (env-only settings), db (engine,
session, base), errors (structured error taxonomy), logging (structlog + request IDs),
rate_limit (differentiated in-memory limiter), gis (GeoJSON validation, haversine),
storage (object-storage abstraction), pagination, security (JWT + hashing), rbac.

## Multi-tenancy model (ADR-0002)

Every tenant-owned table inherits `TenantScoped` → an `organization_id` column with a
foreign key and composite indexes. Enforcement is layered:

1. **Repository pattern** — every query in every service filters by `organization_id`
   taken from the request's auth context (never from client input).
2. **Auth context** — `AuthCtx` resolves user + active organization from the JWT +
   `X-Org-Id` header and carries the permission set; `ctx.org_id` is the only org id
   any query ever sees.
3. **Automated release-blocking tests** — `tests/test_tenant_isolation.py` logs in as
   users of two organizations and asserts cross-reads/cross-writes fail on every
   domain (reports, complaints, devices, alerts, events, vehicles, routes, members,
   audit, media, analytics).
4. **Jobs & notifications** — background handlers resolve the org from the row being
   processed; notifications fan out to per-user rows.

## Request lifecycle

```
Request → request-id middleware → rate limit (per category + client IP)
        → route dependency (JWT decode → user → active org → AuthCtx)
        → permission dependency (require_perm / ensure_perm)
        → router → service (org-scoped queries) → commit
        → structured JSON response (or structured error with request_id)
        → audit entries for security-relevant mutations
```

## Job queue (ADR-0003)

Jobs are rows in PostgreSQL (`jobs` table) claimed with `SELECT … FOR UPDATE SKIP LOCKED`
by an embedded asyncio worker loop (`app.jobs`). This removes a Redis dependency for
small/medium deployments while keeping at-least-once semantics, retries with backoff and
a dead-letter status. Long-running work (route optimization above the inline stop count,
AI batch classification, SLA escalation sweeps, sustainability recompute) runs there.

## Routing engine

Two cleanly separated concerns (ADR-0005):

- **Stop sequencing** — OR-Tools capacitated VRP: multiple vehicles, capacities,
  fill-level-weighted demand, depot start/end. Solver provenance (solver, status,
  solve time, unassigned stops) is stored on the route.
- **Road geometry** — OSRM adapter fetches real polylines/distances when
  `ECOMIND_OSRM_BASE_URL` is configured; otherwise a haversine × configurable road
  factor is used and the route is flagged `geometry_is_estimated=true` (surfaced in UI).

## AI pipeline (ADR-0004)

`app/ai/providers.py` defines a provider-agnostic interface. Registered providers:
OpenAI, Anthropic, Google, and a deterministic **heuristic baseline**. Inference output
is schema-validated (category ∈ org's category list, confidence ∈ [0,1]); out-of-range
values are rejected, and confidence below the acceptance threshold routes the item to
human review. The baseline provider tags every inference `is_simulated=true` so a
demo/dev environment never presents fabricated AI output as real. Prompt-injection
defense: citizen-supplied text is treated as untrusted data, never concatenated into
instructions.

## Sustainability engine (ADR-0006)

- Versioned **emission-factor library** (platform-level, per factor code + version,
  sourced: EPA WARM etc.).
- `recompute` derives **carbon records** from recorded waste treatments, each labelled
  `quality ∈ {measured, estimated, modeled}` with factor code/version, methodology text
  and assumptions JSON — full provenance per row.
- **Avoided emissions** (counterfactual "all diverted waste to landfill") are stored as
  a separate `scope=avoided` record and never summed into net totals. No tradable
  carbon credits exist anywhere in the product; citizens earn non-financial
  recognition points only.

## Frontend architecture

- **React 19 + TypeScript strict**; Vite 6 dev server proxies `/api` to the backend so
  browser code only ever uses relative URLs (no CORS in production behind nginx).
- **Tailwind v4** with `@theme` design tokens (no config file); dark-first design.
- **TanStack Query v5** (15s stale time, 5xx-only retry) for all server state;
  mutations invalidate targeted query keys.
- **HashRouter** — the SPA works from any static file serving without server rewrites
  (ADR-0007).
- **Auth context** — in-memory tokens + localStorage active-org id; `hasPerm()`
  drives navigation so the UI never advertises features the API would reject.
- Design-system primitives and the Leaflet map component are centralized in `ui.tsx` /
  `map.tsx`; pages compose them.

## Data model (core tables)

`users`, `organizations`, `org_memberships`, `org_invitations`, `roles/permissions`,
`operational_units`, `zones`, `waste_categories`, `waste_reports` (+timeline events),
`complaints` (+comments), `collection_points/schedules/events`, `vehicles`,
`driver_profiles`, `routes` (+stops), `devices`, `telemetry_readings`, `alert_rules`,
`alerts`, `ai_inferences`, `media_assets`, `emission_factors`, `waste_treatments`,
`carbon_records`, `notifications`, `reward_ledger`, `audit_events`, `jobs`,
`refresh_tokens`, `password_resets`.

All tenant-owned tables carry `organization_id`; Alembic owns the schema.
