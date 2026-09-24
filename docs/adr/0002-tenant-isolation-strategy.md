# ADR-0002: Tenant isolation — shared schema, repository-layer scoping, release-blocking tests

**Status:** Accepted · **Date:** 2026-09

## Context

Multi-tenant SaaS with a hard requirement: organization A must never reach
organization B's data via API, jobs, notifications, WebSockets (future) or files.
Options: schema-per-tenant, database-per-tenant, or shared schema with a
discriminator column.

## Decision

**Shared schema with `organization_id` on every tenant-owned row**, enforced by:

1. A `TenantScoped` mixin every tenant table inherits.
2. All queries go through service functions that take `organization_id` from the
   server-resolved auth context (`AuthCtx`) — client input never supplies scoping.
3. An **automated cross-tenant test suite that is release-blocking**: two orgs,
   real JWTs, every domain endpoint probed for reads and writes with foreign ids.

## Rationale

- Schema-per-tenant and db-per-tenant make migrations O(n) across tenants and
  complicate connection pooling; shared schema keeps operations O(1) — decisive for
  a platform targeting many small organizations.
- The real risk in shared-schema designs is a single missed `WHERE` clause. We treat
  that as a *test* problem with a permanent suite, not a hope.
- The `X-Org-Id` header switches the active org but is validated against the user's
  memberships — it cannot fabricate access.

## Consequences

- Migrations run once; tenant onboarding is a row insert.
- The isolation suite grows with every new domain (a required checklist step).
- Row-level security (Postgres RLS) was considered as defense-in-depth and remains a
  future hardening option; the repository layer + tests are the contract today.
