# EcoMind-AI Baseline Audit

**Audit date:** 2026-09-18  
**Scope:** Repository discovery only. No application, database, configuration,
or dependency behavior was changed in this phase.

## Evidence reviewed

- Complete project-owned file inventory (excluding dependency directories).
- Root and `docs/` project documentation, including the specification,
  decisions, security, deployment, testing, architecture, AI, IoT, and
  handoff documents.
- FastAPI entry point, configuration, authentication/RBAC, every API router,
  models, schemas, services, AI modules, integrations, and Alembic scripts.
- React/Vite and Expo/React Native entry points and API clients.
- Dockerfiles, Docker Compose, environment examples, test suite, Git status,
  branches, and recent history.

## Current architecture

EcoMind-AI is a modular monolith. A React/Vite web client and an Expo mobile
shell communicate with a FastAPI API. The API uses Pydantic request/response
schemas, SQLAlchemy models and domain services, and PostgreSQL as the intended
system of record. Alembic is the schema migration mechanism. JWT bearer tokens
and named roles (`admin`, `citizen`, `collector`) control access. Docker Compose
starts PostgreSQL 16, the API, and a static Nginx-hosted frontend.

The backend separates routers (`app/api`), domain services (`app/services`),
models (`app/models`), schemas (`app/schemas`), core configuration/security,
and AI/integration adapters. That structure is aligned with the approved
technology direction. It does not yet have repository classes, a universal
audit component, a workflow/approval component, task queue, or CI pipeline.

## Feature baseline

| Area | Status | Findings |
| --- | --- | --- |
| Identity and RBAC | Partial | Public citizen registration, password hashing, JWT login, authenticated-user lookup, and role checks exist. Token refresh/revocation, password reset, verification, role administration, and security-event audit records do not. |
| Waste reports | Partial | Citizens can create/list reports; admins can list and transition them; locations and optional image paths are stored. There is no upload pipeline, malware scan, status history, review record, or consistent organization enforcement. |
| AI classification and assistant | Partial | Deterministic keyword waste/complaint analysis and a local assistant fallback are active and traceable. Optional Ollama/Hugging Face adapters exist but are not selected by `AIInference`; external output validation/normalization is not implemented. |
| Collections and routes | Partial | Admin assignment, collector updates, nearest-neighbor routes, optional OSRM legs, and notifications exist. Assignment and route generation are direct state changes without review/audit and have incomplete tenant checks. |
| Complaints | Partial | Creation, keyword triage, status transitions, ownership checks for linked reports, notifications, and complaint-specific history exist. AI recommendations are not explicitly approved/rejected and no generic audit event is written. |
| Rewards and carbon | Partial / caution | Reward activities and a marketplace-shaped carbon data model exist. Carbon documentation correctly disclaims regulated/verified credits, but the API allows immediately completed earn/buy actions without methodology, settlement, approval, or audit controls. |
| Environmental, IoT, municipality | Partial | Admin CRUD-style sources, readings, bins, municipalities, and service areas exist. MQTT/sensor integrations and municipal sync are adapter/placeholders; `/sync` records a completed internal log rather than invoking an external system. |
| Analytics and notifications | Partial | Admin dashboard/distribution queries and in-app notifications exist. Analytics are not consistently organization-scoped; no background delivery, retention policy, or operational monitoring exists. |
| Realtime | Partial | A token-gated `/ws/events` endpoint and in-memory connection manager exist. Documentation says realtime is inactive; no durable broker, horizontal-scale support, authorization event policy, or browser/mobile integration is evident. |
| Web frontend | Partial | A functional single-file React application supplies public pages, login, dashboard views, and API calls. It is not modularized into pages/components/auth state, has no test suite, and relies on localStorage bearer tokens. |
| Mobile | Partial | Expo shell provides dashboard/report views and AsyncStorage bearer-token API client. Camera uploads, offline queues, push notifications, collector workflows, and device builds remain intentionally unimplemented. |

## Database and migration status

- Models cover roles, users, organizations, reports, collections, routes,
  complaints/history, notifications, rewards, carbon, environmental records,
  municipalities/service areas, and AI operation logs.
- Alembic has one linear head: `c7d9e1f3a205` (`add organization scope
  foundation`). `python -m alembic heads` confirms a single head.
- Migrations are additive in the visible history; no destructive migration was
  identified.
- A running PostgreSQL migration/upgrade test was not performed in this audit.
  The test suite uses no database fixture or endpoint client.
- Several schema concerns require caution before production changes: status
  values are free-form strings rather than database constraints/enums;
  `organization_id` is nullable; foreign-key/tenant invariants are not applied
  uniformly; no generic audit or approval tables exist; and no report status
  history table is present.

## Security risks and controls

Existing controls include environment-sourced configuration, production
rejection of short/known placeholder JWT secrets, bcrypt via Passlib, JWT
validation, role checks, Pydantic field validation, CORS middleware, generic
error responses, request IDs, security headers, and a process-local rate
limiter.

Priority risks/gaps:

1. Organization/tenant isolation is inconsistent. Many collections, routes,
   analytics, carbon, environmental, and municipality queries are global or
   only partially scoped; this requires BOLA/IDOR testing before production.
2. Access tokens have no refresh rotation, revocation, device/session
   management, password reset, or email verification. Web tokens are stored in
   localStorage, increasing XSS impact.
3. The rate limiter is in-memory per API process and can be bypassed across
   instances; it has no identity-aware policy or shared store.
4. `image_path` accepts a string but there is no authenticated object-storage
   upload, content-type/size validation, malware scanning, or access policy.
5. Authentication, administrative changes, collection/route operations,
   marketplace actions, and configuration changes do not create a generic,
   tamper-resistant audit trail. `AIOperationLog` is AI telemetry only.
6. Docker Compose exposes PostgreSQL and API ports and has no reverse proxy,
   TLS, secret manager, non-root/container hardening, backup job, or resource
   limits. It is a local/development deployment baseline, not a production
   deployment.

## AI and agent status

The active AI path is deliberately limited: keyword classifiers and a safe
local guidance fallback. It does not execute generated SQL, shell commands,
filesystem operations, arbitrary code, or external side effects. Classification
and complaint analysis retain model/provider/version/confidence/latency
metadata in report/complaint records and `ai_operation_logs`.

The adapters for Ollama and Hugging Face are replaceable integration code, but
the active `AIInference` constructor always selects `KeywordWasteClassifier`.
Ollama returns raw response text as a label and Hugging Face returns provider
labels; neither is currently normalized against approved waste categories or
wired through structured Pydantic validation. Assistant responses are not
persisted/audited. No autonomous agent/workflow executor is present.

## Technical debt and duplication

- `frontend/src/App.tsx` combines public marketing pages, authentication,
  dashboard state, role mapping, route layout, and domain views in one large
  component rather than the documented modular frontend structure.
- The frontend maps numeric role IDs locally (`4/5/6`) while backend roles also
  retain legacy numeric IDs. Role names are checked at runtime, but the
  numeric contract remains duplicated and brittle.
- Report lifecycle logic exists in `waste_report_service`, but collection
  creation assigns `report.status` directly. Lifecycle authority is therefore
  split.
- The project uses `unittest`, although the approved fixed direction names
  pytest. There are no pytest configuration/files.
- Some documentation describes a future/inactive realtime deployment while
  the backend includes a WebSocket endpoint; feature claims must be reconciled
  before release.
- There is no project-owned CI/CD configuration (`.github/workflows`,
  Jenkinsfile, Makefile, or equivalent). Files found under dependency folders
  are third-party metadata, not project automation.

## Test and quality baseline

Completed during audit:

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app alembic tests
.\.venv\Scripts\python.exe -m alembic heads

cd ..\frontend
npm run build
npm run lint
```

Results: 19 unit tests passed; Python compilation passed; a single Alembic head
was reported; frontend build and lint passed. No project-owned CI was found.

Missing coverage includes PostgreSQL migration upgrades/downgrades, API
integration tests, authentication failures, RBAC and BOLA/IDOR scenarios,
tenant isolation, lifecycle/workflow approval, audit persistence, WebSocket
authorization, external provider failure/invalid output, upload security,
concurrent carbon purchase behavior, frontend tests, mobile typecheck/build,
and deployment smoke/security tests.

## Deployment and operational gaps

- Compose performs `alembic upgrade head` on API startup, but migration rollout
  is not separately controlled or tested against a production-like database.
- No CI/CD, artifact promotion, environment separation, release strategy,
  automated backups/restore verification, centralized logging, metrics,
  tracing, alerting, SLOs, or incident runbook execution is present.
- Health, liveness, and readiness endpoints exist. Database health is checked
  synchronously from request handlers.
- The public UI displays unsourced “Live operations” metrics (`92%`, `1.4k`).
  These must be sourced or explicitly labelled illustrative/simulated per the
  specification.

## Contradictions identified during audit

1. The project specification names a compact report vocabulary including
   `reviewed`; the implementation uses a richer state machine with `reported`,
   `ai_analyzed`, `verified`, `scheduled`, `verified_collection`, and
   `resolved`. **Resolved in Phase 1:** the GitHub-tracked project
   specification is canonical; safe migration/compatibility work remains.
2. The project contract requires a persisted human-in-the-loop flow where
   applicable: proposal, pending review, approve/reject, execution after
   approval, result, and audit. **Resolved in Phase 1:** current AI is advisory
   and ordinary human-admin actions remain RBAC-controlled; any future
   AI-initiated action requires the full persisted approval workflow.
3. `docs/ARCHITECTURE.md` calls realtime inactive, while `app/main.py`
   registers a WebSocket endpoint. **Resolved in Phase 1:** it is an
   experimental backend capability, not a supported live deployment feature.
4. Carbon documentation disclaims recognized carbon credits, while endpoints
   expose a completed marketplace flow. **Resolved in Phase 1:** it is
   demonstrative only and must not claim verified credits or financial trading.
5. `PROJECT_STATUS.md`/handoff say Phase 0 is current, while the latest Git
   commit message claims stage 0 completion. This audit treats Phase 0 as in
   progress because the requested baseline record and release-gap decisions are
   only now being completed.

## Files requiring caution

- `backend/app/core/security.py`, `backend/app/core/config.py`, and
  `backend/app/main.py`: authentication, startup validation, middleware, and
  WebSocket behavior; security-sensitive changes.
- `backend/app/core/roles.py` and every router using `RoleID`: legacy numeric
  role coupling affects authorization and clients.
- `backend/app/api/collections.py`, `routes.py`, `carbon.py`,
  `environmental.py`, `municipalities.py`, and `analytics.py`: global or
  partially organization-scoped queries need coordinated authorization review.
- `backend/app/services/waste_report_service.py` and
  `backend/app/api/waste_reports.py`: canonical lifecycle behavior must change
  together with client schemas and tests.
- `backend/alembic/versions/`: migrations are authoritative; only additive,
  reviewed migrations should be introduced.
- `backend/app/ai/*` and `backend/app/integrations/ai/*`: external provider
  output must be validated before it can influence workflow decisions.
- `frontend/src/App.tsx` and `frontend/src/services/api.ts`: large coupled UI
  surface and browser token handling; avoid a broad rewrite during Phase 0.
- `docker-compose.yml`, Dockerfiles, and `.env.example` files: deployment and
  secret-bearing configuration; changes require operational/security review.
- `docs/AGENTS.md.txt`: pre-existing untracked repository instructions; this
  file was not modified by the audit.

## Git baseline

- Current branch: `master`, at `c5a61b3` (`completed stage 0 and some changes`)
  and aligned with `origin/master` at audit time.
- Other local branches: `legacy-before-claude` and
  `copilot/worktree-2026-09-15T17-19-51`.
- Recent history includes platform implementation, website/deployment work,
  Claude control documentation, and the stage-0 commit.
- Working tree before this audit contained untracked `docs/AGENTS.md.txt`.
  This audit adds only this requested document.

## Phase 0 conclusion

The repository is a credible modular development baseline, not a
production-ready system. The next phase should resolve the lifecycle/HITL
decisions and then implement only bounded, additive schema/security/workflow
work with integration tests and updated documentation. No broad refactor is
recommended from this baseline audit.
