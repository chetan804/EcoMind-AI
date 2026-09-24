# Security documentation

## Authentication

- **Password hashing**: Argon2id (argon2-cffi defaults: 64 MiB, t=3, p=4) — no
  bcrypt/SHA anywhere. Minimum password length 10.
- **JWT access tokens**: 30-minute default, HS256 with an env-provided high-entropy key.
  Production refuses to boot without `ECOMIND_SECRET_KEY`.
- **Refresh rotation with revocation**: refresh tokens are single-use rows in the
  database; every use rotates the token and revocation lists kill whole families on
  logout/password change. A replayed refresh token is rejected.
- **Password reset**: single-use, expiring tokens (60 min default), delivered out of
  band (email sending is integration-ready; the token endpoint is implemented).
- **Rate limiting** (differentiated, per client IP + category):
  auth 15/min · writes 60/min · AI 20/min · uploads 30/min · telemetry 600/min ·
  reads 600/min. Tests disable limits via env so suites stay deterministic.

## Authorization (RBAC)

- 8 roles (org_admin, ops_manager, field_supervisor, collector,
  sustainability_analyst, citizen, viewer + platform_admin flag) mapping to ~50
  granular permissions (`report:resolve`, `route:generate`, `alert:manage`, …).
- **Every** route declares its permission dependency; services re-check ownership for
  "own vs all" access (e.g. a citizen may read their own report, ops may read all).
- The frontend renders navigation from the same permission set — but the UI is never
  the enforcement point; the API is.

## Tenant isolation (release-blocking)

- All tenant data rows carry `organization_id`; every service query filters by the
  org resolved from the **JWT + membership**, optionally switched via the `X-Org-Id`
  header (validated against the user's memberships).
- Automated suite (`tests/test_tenant_isolation.py`) proves org A cannot read or
  write org B's reports, complaints, devices, alerts, events, vehicles, routes,
  members, audit, media or analytics — including by guessing ids.
- Background jobs and notification fan-out resolve the org from the row, never from
  user input.

## Input & upload security

- Pydantic v2 validation on every payload; latitude/longitude range checks; GeoJSON
  polygon validation (Shapely) for zones.
- Uploads: MIME allow-list (JPEG/PNG/WebP), 10 MiB cap, extension/spoofing checks,
  SHA-256 checksums stored, files served with `X-Content-Type-Options: nosniff` and
  attachment semantics; never executed; uploads stored outside the web root.
- No SQL string building anywhere — parameterized ORM queries only.

## AI safety

- Provider-agnostic abstraction; **no model names hard-coded** in the codebase.
- Citizen-supplied text is untrusted data: it never enters prompt instructions
  (injection defense-in-depth), and inference outputs are schema- and range-validated
  (category must exist in the org's category list; confidence ∈ [0,1]).
- Low-confidence results are routed to human review; the deterministic baseline
  labels every inference `is_simulated` so no environment ever shows fabricated AI
  output as real.

## Error handling & logging

- Structured JSON errors with stable codes and a `request_id`; **no stack traces,
  no internal details, no secrets** in responses.
- structlog JSON logs carry request ids; secrets are never logged (auth flows log
  events, not credentials).

## Transport & headers

- Same-origin deployment (nginx) by default; CORS is configurable and should be
  restricted in production. Security headers (`X-Content-Type-Options`,
  `X-Frame-Options: DENY`, `Referrer-Policy`) are set at the proxy.
- TLS termination at the load balancer/proxy is the reference pattern.

## Device authentication (IoT)

- Devices authenticate with per-device API keys (hashed at rest, returned exactly
  once at registration/rotation) via `X-Device-Key` — **device ids alone are never
  trusted**. Ingestion is rate-limited per device and strictly schema-validated.

## Audit trail

- Security-relevant mutations (auth events, member/role changes, device registration,
  key rotation, route/ops changes) write immutable audit rows with actor, before/after
  diffs and request id, queryable by `audit:read` roles.

## Reporting / disclosure

Found a vulnerability? Please report privately to the repository owner — do not open
a public issue with exploit details.
