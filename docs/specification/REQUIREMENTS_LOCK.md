# EcoMind-AI Requirements Lock

**Status:** Locked. Resolutions below are derived from the tracked GitHub
`PROJECT_SPEC.md`, which is the normative requirement source where the
implementation differs.

## Evidence and authority

The lock is based on `PROJECT_SPEC.md`, `DECISIONS.md`, `README.md`, the
operational documentation, the baseline audit, and implemented API/UI/model
surfaces. No separate project proposal, abstract, diagrams, or database-design
artifact exists in this repository; none was inferred.

## Objective and problem

EcoMind-AI is a role-based, API-driven smart waste-management and environmental
sustainability platform. It must let communities report waste/environmental
issues, municipal staff operate collection workflows, and administrators see
auditable operational information. AI may provide bounded recommendations, but
the authoritative system is the FastAPI/PostgreSQL application—not an AI model,
browser, mobile client, or external integration.

## Actors

| Actor | Locked responsibility |
| --- | --- |
| Citizen | Register/login; create and view own reports/complaints; view own collections, notifications, rewards, carbon balance/transactions, and permitted assistant guidance. |
| Collector | View only assigned collections/routes and update assigned collection lifecycle states. |
| Administrator | Operate reports, collection assignment, routes, complaint triage, municipalities, environmental records, analytics, and controlled sustainability functions. |
| AI provider | Returns an untrusted recommendation only; cannot authenticate, authorize, execute actions, write SQL, or cause external side effects. |
| IoT/routing/municipal provider | Optional adapter boundary; no live provider may be represented as active unless configured, authenticated, tested, and documented. |

## Functional requirements

| ID | Locked requirement |
| --- | --- |
| FR-01 | Citizens can register as citizens only and authenticate with JWT bearer tokens. |
| FR-02 | The backend enforces ownership and RBAC; clients never access PostgreSQL directly. |
| FR-03 | Citizens can create, view, and track their own waste reports containing type, description, textual location, optional coordinates, and future-safe media reference. |
| FR-04 | Authorized staff operate reports using the canonical lifecycle `submitted → reviewed → assigned → in_progress → collected`, with permitted terminal `rejected`/`cancelled` outcomes. Collection-specific scheduling/progress details must not create undocumented report states. |
| FR-05 | AI classification and complaint analysis produce validated, traceable recommendations; a human remains accountable for important operational decisions. |
| FR-06 | Administrators can assign collectors and generate/view collection routes; collectors can only act on their assignments. |
| FR-07 | Citizens can submit and track complaints; administrators can triage, assign, resolve/reject, and notify the citizen. |
| FR-08 | Users can view only their notifications and reward activity/balance. |
| FR-09 | Administrators can manage municipality/service-area and environmental/smart-bin reference records. Live IoT ingestion is not in scope for the baseline. |
| FR-10 | Authorized sustainability records are clearly demonstrative until a verified methodology and approved workflow exist. |
| FR-11 | Administrators can obtain organization-scoped operational analytics. |
| FR-12 | Important security-sensitive and operational state changes are auditable. Current AI is advisory only; no AI output may execute an action. Any future AI-initiated action must use persisted proposal → pending review → approve/reject → execute → result → audit. |

## Non-functional requirements

- PostgreSQL is authoritative; SQLAlchemy models and Alembic migrations own
  persistence/schema change.
- FastAPI/Pydantic validates API data; React/TypeScript and mobile clients use
  authenticated backend APIs only.
- Secrets are environment-sourced; passwords are hashed; JWT/RBAC validation,
  predictable errors, request correlation, CORS, and safe headers are retained.
- AI output is untrusted and must be typed, category-bounded, traced, and
  unable to invoke SQL, shell, filesystem, arbitrary code, or side effects.
- Production claims require organization isolation, security testing, database
  migration testing, backups/recovery, deployment monitoring, and truthful
  labeling of simulated/illustrative data.
- The modular monolith remains the approved architecture. No microservices,
  new infrastructure, destructive migrations, or technology replacement are
  authorized by this lock.

## Module, API, and UI responsibility lock

| Module | Backend/API authority | UI responsibility |
| --- | --- | --- |
| Identity | `/users`, `/auth/login`, `security`, `roles` | Registration/login/profile/session presentation only. |
| Reports/collections/routes | `/waste-reports`, `/classification`, `/collections`, `/routes` and domain services | Citizen report flow; collector assignment/route views; admin review/operation views. |
| Complaints/notifications | `/complaints`, `/notifications` | Citizen submission/history and notification display; admin triage display. |
| Sustainability | `/rewards`, `/carbon` | Balances/history and demonstrative labeling only. |
| Municipal/environmental | `/municipalities`, `/environmental`, integrations | Admin management views; label simulator/future integrations. |
| Insights/assistant | `/analytics`, `/assistant/ask`, `app/ai` | Display analytics; send guidance prompt and display bounded response. |
| Audit/approval | Audit service is required for important operations; approval workflow is required before any future AI-initiated action | Audit and, where a future AI action is proposed, pending-review/approve/reject/outcome displays. |

## Data, context, and security boundaries

- The API is the sole authority for tenant/organization, role, ownership,
  lifecycle, reward, approval, and audit decisions.
- User text, locations, media references, device/IoT payloads, routing results,
  and all AI responses are untrusted input until validated.
- The UI may hold presentation/session state but cannot select roles, alter
  approval state, or calculate authoritative balances/metrics.
- Audit data must omit secrets, credentials, tokens, password hashes, and
  unnecessary prompt/body content.

## In scope

The modules in FR-01 through FR-12, production hardening necessary for them,
modular React UI, bounded adapters/fallbacks, Alembic-backed additions, pytest
coverage, operational documentation, and deployment readiness evidence.

## Out of scope until explicitly approved

Live smart-bin/MQTT ingestion, traffic-aware/OR-Tools routing, autonomous
agents, image ML, third-party model enablement, financial or verified carbon
trading, public municipal/government integrations, microservices, PostGIS,
and a new infrastructure platform.

## Resolved source conflicts

### RC-01: Canonical report lifecycle

The GitHub-tracked `PROJECT_SPEC.md` is authoritative: report statuses are
`submitted`, `reviewed`, `assigned`, `in_progress`, `collected`, `rejected`,
and `cancelled`. The implementation-only `reported`, `ai_analyzed`,
`verified`, `scheduled`, `verified_collection`, and `resolved` values are not
requirements and must be retired/mapped through a safe, additive migration and
compatibility plan before a production release. This lock does not authorize
that migration.

### RC-02: Human-in-the-loop scope

The source documents define the current AI features as deterministic
classification/analysis and safe guidance, not autonomous agents. Consequently,
AI output is advisory: a human administrator performs review, assignment,
triage, configuration, or sustainability decisions through authorized APIs.
No additional approval queue is required for an ordinary action directly
performed by that authorized human. If a future AI feature proposes an action
that could change data, dispatch work, or cause an external effect, the full
persisted approval workflow in FR-12 is mandatory before execution.

### RC-03: Realtime and carbon claims

The WebSocket implementation is an experimental backend capability, not a
supported live/realtime deployment feature until client integration, durable
delivery, authorization policy, and operational evidence exist. Carbon records
and marketplace-shaped endpoints are demonstrative sustainability records only;
they must not be labeled or marketed as verified credits or real financial
transactions. The public UI and documentation must reflect these restrictions.

## Measurable completion criteria

The locked scope is complete only when every traceability row has passing
tests, acceptance criteria are met, all required migrations upgrade on
PostgreSQL, authorization/tenant tests pass, AI invalid-output tests pass,
audit criteria pass, any future AI-initiated action satisfies the approval
criteria, frontend/mobile flows consume the real API, and deployment/restore/
security evidence is recorded.
