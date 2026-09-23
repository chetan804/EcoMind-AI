# EcoMind-AI — Build Report & Final Audits

**Date:** 2026-09-23 · **Commits:** `d7b3169` (backend) · `4cf951e` (frontend) · `c7c142e` (docs/deploy/CI/hardening)
**Scope:** Clean rebuild of the platform per the Final Master Build Prompt (phases 0–18).

---

## Phase reports

### Phase 0–5 — Foundations, tenancy, auth, RBAC, citizen reporting
**Completed:** FastAPI + SQLAlchemy 2 (async) + Alembic + Pydantic v2 skeleton; env-only
config (`.env.example`, production refuses to boot without a secret key); `TenantScoped`
mixin on every org-owned table; Argon2id hashing; JWT access + single-use rotating
refresh tokens with family revocation; 8 roles / ~50 permissions enforced per request;
org self-service (create, join open orgs, zones with GeoJSON validation, units,
members, invitations); citizen waste reports with anonymous mode, photos, geo validation.
**Tests:** unit + integration suites per domain.
**Decisions:** ADR-0001 (modular monolith), ADR-0002 (isolation strategy).
**Risks:** none open.

### Phase 6–9 — Complaints, collection ops, fleet, routing
**Completed:** complaint lifecycle (submitted→triaged→assigned→in_progress→resolved/closed)
with SLA due dates, comments (public vs internal), assignment, resolution summaries;
collection points/schedules/events with measured weights + contamination flags; fleet
registry (vehicles, drivers, positions with simulated-labelling); OR-Tools capacitated
VRP route generation with solver provenance, draft→approved→in_progress→completed
workflow, per-stop field execution; OSRM adapter with labelled straight-line fallback.
**Changed vs. spec:** routing split into sequencing vs. geometry layers (ADR-0005) — a
superior separation to a monolithic "routing service".
**Tests:** lifecycle, permission, and isolation suites.

### Phase 10–11 — IoT, AI
**Completed:** device registry with hashed per-device API keys (returned once), key
rotation, authenticated `X-Device-Key` ingestion with strict payload validation,
configurable threshold alert rules → alert engine with cooldown + dedup; explicitly
labelled telemetry simulator (`is_simulated=true`, off by default). AI provider
abstraction (OpenAI/Anthropic/Google/heuristic baseline), schema+range+confidence
validation, human-review routing below threshold, injection defense (citizen text is
data, never instructions).
**Decisions:** ADR-0004. **No fabricated AI output is possible** — the baseline labels
itself simulated.

### Phase 12–13 — Sustainability, analytics
**Completed:** versioned emission-factor library (EPA WARM sourced); recompute job
deriving carbon records from treatments with quality labels (measured/estimated/modeled)
and full provenance (factor code+version, methodology, assumptions); avoided emissions
as a separate modeled scope; role-specific dashboards (operations/citizen/executive)
computed only from real rows; CSV exports.
**Decisions:** ADR-0006 (no tradable carbon credits; points are recognition only).

### Phase 14 — Platform: jobs, audit, media, notifications, rewards
**Completed:** PG-backed job queue (`SKIP LOCKED`) + embedded worker (ADR-0003); audit
log with before/after + request ids; media upload security (MIME allow-list, size cap,
checksums, org-scoped retrieval, storage abstraction — ADR-0008); in-app notifications;
rewards ledger + leaderboard.

### Phase 15 — Frontend (this phase)
**Completed:** React 19 + TS strict + Vite 6 + Tailwind v4 SPA: landing, auth (demo
quick-fill, public-org join), onboarding wizard; role/permission-aware shell (org
switcher, notification badge, DEMO/SIMULATED badges); citizen dashboard + 3-step report
wizard (photo upload, geolocation/map tap, AI result with confidence and review note);
field route execution (touch-first); command center (layered live map, alerts, fleet);
routes list/wizard/detail with solver provenance and estimated-geometry badges; ops
reports triage (low-AI-confidence filter), complaints (SLA, comments, assignment),
fleet, IoT devices (one-time key display), collection events; sustainability
(treatment mix, scopes, records ledger, factor library, recompute) and executive
dashboards; admin (members/roles/invites with one-time token, org settings, alert
rules, audit log); notifications and profile pages.
**Changed vs. spec:** HashRouter + relative-URL API client behind a proxy (ADR-0007) —
works from any static host, no CORS surface; navigation renders from permissions so the
UI never advertises what the API would reject.
**Tests:** 22 vitest tests (formatters, API client error/refresh/header semantics);
typecheck + production build clean; **25 endpoints smoke-tested through the dev proxy
against the live seeded API, plus driver/citizen role flows incl. an expected 403.**

### Phase 16–18 — Docs, deployment, CI
**Completed:** README + PRODUCT, ARCHITECTURE, DEVELOPMENT, DEPLOYMENT, SECURITY,
PRIVACY, API, OPERATIONS, KNOWN_LIMITATIONS, ROADMAP + 8 ADRs; Dockerfiles (non-root
API with migration entrypoint + healthcheck; nginx frontend with security headers and
asset caching) + docker-compose (postgres, api, web, volumes); GitHub Actions CI
(backend ruff + pytest against a real Postgres service; frontend typecheck + tests +
build; Docker image builds).
**Issues:** Docker builds could not be executed in the authoring sandbox (no Docker
daemon) — CI job `docker` is the validation gate; Dockerfile reviewed line-by-line
(entrypoint permissions, package layout, non-root user, healthcheck verified logically).

---

## Demo environment (seeded, fully labelled)

Org **Aurora Municipal Corporation** (`aurora-demo`, `is_demo=true`): 4 zones, 52
collection points, 6 vehicles, 22 members (admin/ops/supervisor/analyst/3 drivers/15
citizens), 14 simulated IoT devices with 5 days of telemetry, 38 waste reports with
simulated AI inferences, 18 complaints across SLA states, ~30 days of collection
events (468 events, 94% completion), 4 optimized routes (solver: ortools-cvrp,
geometry labelled estimated), open alerts, notifications, rewards ledger. Sustainability
totals: 104.8 t treated · 65.5% diversion · 27.3 t CO2e net · 33.6 t avoided (modeled).
Logins: `admin@aurora.demo` … password `EcoDemo2026!` (quick-fill on the login page).

---

## Final audit 1 — Engineering

- **Backend:** 52/52 tests green (incl. release-blocking tenant-isolation suite);
  ruff clean across app/tests/scripts; real migrations in tests (no mocked DB);
  async throughout.
- **Lint gate found three real defects, fixed at root cause:** (1) `GET
  /organizations/mine` referenced an undefined name → runtime 500 (regression test
  added); (2) complaints service kept a never-persisted `ai_inference_id` assignment;
  (3) `seed_demo --reset` left demo users behind (users are not org-scoped), breaking
  re-runs — reset now removes them by the reserved demo email domain.
- **Frontend:** strict TS clean; 22/22 vitest; production build 4 chunks (vendor/map/
  charts/app, all < 500 kB); every API call typed against verified response shapes
  (all 25 endpoints probed against the live API).
- **Repo hygiene:** no secrets committed (`.env` gitignored; `.env.example` only);
  build artifacts ignored; demo data seeded by script, not dumped into git.
- **Verdict: PASS.** Debt registered in KNOWN_LIMITATIONS (rate-limiter sharing,
  WebSocket push, i18n).

## Final audit 2 — Security

- Argon2id; JWT rotation + revocation; production secret enforcement; differentiated
  rate limits; permission checks on every route; ownership checks for own-vs-all reads.
- Tenant isolation: repository-layer scoping + automated cross-tenant suite
  (release gate) — the platform's #1 security requirement.
- Uploads: allow-list/cap/checksum/nosniff, stored outside web root; devices
  authenticate with per-device keys (ids never trusted); AI output schema/range
  validated; citizen text never enters prompt instructions; structured errors leak
  no internals; audit trail on security-relevant mutations.
- **Verdict: PASS** with documented hardening options (Postgres RLS, Redis limiter)
  recorded as future work.

## Final audit 3 — Product

- Every persona has a real surface: citizen → report/track/impact; driver → field
  execution; supervisor/ops → command center + triage; analyst → sustainability;
  admin → members/settings/audit; executive → KPIs.
- The "no fake features" rule holds: AI without a provider is labelled SIMULATED;
  estimated route geometry is badged; avoided emissions stay separate; empty orgs
  render empty states; demo data is badged everywhere it appears.
- **Verdict: PASS.** Gaps (email delivery, mobile shells, offline mode) are in
  KNOWN_LIMITATIONS/ROADMAP, not hidden.

## Final audit 4 — UX

- Dark-first coherent design system (tokens, panels, chips, badges, focus-visible,
  reduced-motion support); mobile-first field UI with large touch targets; wizard
  patterns for complex flows (report, route generation); destructive/skip actions
  always carry reasons; forms validate client-side and surface server errors in place.
- Accessibility: labelled inputs, aria labels on icon buttons, keyboard-focusable
  navigation, color-coded statuses always paired with text.
- **Verdict: PASS.** Known: map click-to-place uses a projection approximation at
  fixed zoom (documented in code); fine-grained a11y audit pending real screen-reader
  testing (roadmap).

---

## Decisions (all recorded as ADRs)

0001 modular monolith · 0002 shared-schema isolation + release-blocking tests ·
0003 Postgres job queue · 0004 provider-independent AI with labelled baseline ·
0005 sequencing/geometry separation · 0006 sustainability provenance, no credits ·
0007 same-origin HashRouter SPA · 0008 in-process limiter + storage seam.

## Risks

| Risk | Mitigation |
| --- | --- |
| Docker images untested in sandbox | CI builds both images on every push; Dockerfiles hand-verified |
| In-process rate limiter under horizontal scale | Documented (ADR-0008) with revisit trigger; single-box reference deployment |
| Estimated geometry mistaken for real | Label travels in API + UI badge; OSRM is config-only |
| Prompt-injection via citizen text | Data-not-instructions pipeline + output validation + review path |

## Next

1. Merge to master and let CI validate Docker builds.
2. Wire email delivery (tokens already exist) — ROADMAP item 1.
3. WebSocket push for command center/field — ROADMAP item 2.
4. Deploy a public demo environment with the seeded org.
