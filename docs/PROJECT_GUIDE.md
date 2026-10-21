# EcoMind AI — the complete guide for a beginner

This guide explains the whole project to someone who knows nothing about it. You do not need to be a programmer for parts 1–6. Parts 7–12 are for people who want to look inside or run it. Facts here were checked against the code on 2026-10-21 (see `docs/project-completion/PROJECT_AUDIT_REPORT.md` for how). Where something is missing or unproven, this guide says so.

**Contents**
1. What EcoMind AI is
2. The problem it addresses
3. Who uses it (the five roles)
4. The big workflow: from a dirty street to a reward
5. Every feature, in plain words
6. The artificial intelligence parts and what they can and cannot do
7. How it is built (technology without jargon)
8. A tour of the folders
9. The database
10. Security
11. How to run it
12. Honest status: what works, what does not
13. Glossary
14. Where to read more

---

## 1. What EcoMind AI is

EcoMind AI is a **web application for managing waste in a city or district**. It is used in a browser (computer or phone). It connects four groups of people who normally work separately:

- residents who see waste and want it collected,
- field crews who collect it,
- facility staff who sort and recycle it,
- managers who plan the work and need to know what is happening.

Around that core it adds: a photo-based **AI waste identifier**, **forecasts** of how much waste to expect, **alerts** about unusual weeks, a **marketplace** for surplus material, **rewards** for residents, **material passports** that trace a batch of material, and a **help assistant**.

It is a final-year-style engineering project. It has **never been deployed** to real users, and it does not contain real city data. The demonstration records you may see are invented and labelled.

## 2. The problem it addresses

Typical problems in municipal waste handling:

1. **Reports get lost.** A resident calls or messages about a dumped pile; nobody tracks whether it was collected.
2. **Crews work without a plan.** Routes are decided by habit, not by where the work is.
3. **Nobody can prove what happened to the material.** "It was recycled" is a claim without a record.
4. **Planning is guesswork.** Without history, nobody knows next month's volume.
5. **Residents get no feedback** and so stop reporting.
6. **Sorting mistakes** at home contaminate recycling.

EcoMind AI gives each problem a screen: reports with statuses, task and route planning, recovery records with a second-person check, forecasting from history, notifications and points, and a sorting guide with a classifier.

## 3. Who uses it (the five roles)

Every account has one or more **roles**. A role decides which menu items appear and what the server will allow. Anyone who signs up on the public page starts as a **Citizen**. Only an administrator can give other roles.

| Role | In real life | Main things it can do | Things it cannot do |
|---|---|---|---|
| **Citizen** | Resident | Report waste (with a photo and place); report community incidents; classify a photo; read the sorting guide; browse facilities and zones; ask for items in the marketplace; see points and redeem rewards; use the help assistant; open support requests | See other people's reports; see tasks, routes, vehicles or analytics; offer marketplace items |
| **Collector** | Driver or field worker | See all waste reports; see tasks; **start and complete tasks assigned to them, recording the weight collected**; see route plans and vehicles; share their live position; report incidents; browse the marketplace | Create or assign tasks; verify reports; file waste reports; earn points |
| **Facility operator** | Staff at a recycling or processing site | Review uncertain AI classifications; **record material recovery**; **create material passports and record custody events**; offer items in the marketplace; see reports and tasks | Verify their own recovery records; manage tasks, vehicles or users |
| **Manager** | Operations manager | Everything an operator does, plus: **verify or reject waste reports; create, assign and cancel tasks; plan and publish routes; manage vehicles, facilities and zones; verify recovery records; triage incidents; manage rewards and marketplace; edit the sorting guide; run forecasts and anomaly scans; read analytics; see the user list; handle support requests** | Change user roles; read the audit log; manage AI models |
| **Administrator** | System owner | All 48 permissions, including **user and role management, the audit log, system status details, AI model management** | — |

An account can hold several roles (for example administrator and citizen). Permissions add together. The five roles hold 13 (citizen), 15 (collector), 15 (operator), 36 (manager) and 48 (administrator) of the 48 permissions.

Why separate "who verifies": a record entered by one person must be verified by a different person, so one person cannot invent a recovery figure and approve it alone.

## 4. The big workflow: from a dirty street to a reward

This is the central story. Each step is a real screen.

1. **A citizen reports waste.** *Reports → Report waste.* They give a title, a place (typing latitude and longitude, using "Use my current location", or picking on the map) and optionally a photo and an estimated weight. Status: **submitted**.
2. **A manager reviews it.** The report moves to **under review**, then **verified** (it is real) or **rejected** (with a recorded reason).
3. **The manager creates a collection task** from the verified report (*Create collection task*). The task copies the place. Status: **pending**.
4. **The manager assigns a collector** and optionally a vehicle. Status: **assigned**. The collector is notified.
5. *(Optional)* **The manager plans a route** that orders several tasks into the shortest stop sequence (straight-line distances), then **publishes** it.
6. **The collector starts the task** (**in progress**), may log field events, and shares their position if they choose.
7. **The collector completes the task with the collected weight in kg.** Status: **completed**.
8. **The reporting citizen is rewarded and notified.** Points = weight × points-per-kg (default 10), at least 1. The citizen sees "Your reported waste was collected". Points appear in their ledger. Collectors and operators earn no points. No carbon or environmental saving is claimed, because no sourced coefficient exists.
9. **At the facility**, an operator **records recovery** (weight processed, weight recovered, method). A manager **verifies** it. Only verified records count in the recovery rate.
10. **An operator may create a material passport** for a batch, add custody events (moved, received, processed) and link a verified recovery record. "Check integrity" confirms the custody history has not been altered.
11. **Managers see the results** in analytics, the dashboard, forecasts and anomaly alerts.

Side stories: a citizen **redeems points** for a reward and gets a **claim code**, which staff hand over; a resident **reports an incident** (illegal dumping, overflowing bin…) that a manager triages; someone **offers surplus material in the marketplace** and another requests it.

**Status words**
- Waste report: submitted → under review → verified or rejected → closed
- Task: pending, assigned, in progress, completed, failed, cancelled
- Route plan: draft, published, in progress, completed, cancelled
- Incident: open, acknowledged, in progress, resolved, dismissed
- Recovery record: pending, verified, rejected
- Passport: active, in processing, recovered, retired
- Support ticket: open, in progress, resolved, closed
- Marketplace listing: draft, published, reserved, closed
- Vehicle: available, in service, maintenance, retired

## 5. Every feature, in plain words

Menu names are exactly as they appear in the sidebar.

| Menu item | Who sees it | What it does |
|---|---|---|
| **Dashboard** | everyone | A welcome page. Citizens see shortcuts. Managers and administrators see key numbers (kg collected, open tasks, recovery rate, anomalies), a weekly chart, a status chart and a map of fleet and facilities. |
| **Analytics** | manager, administrator | Executive figures over time. Every number states its source. |
| **Classification** | everyone | Upload a photo and get a material class with a confidence and sorting advice. **Today it says "No classification model is active"** and does not analyse anything. |
| **Review queue** | operator, manager, administrator | A person confirms or corrects uncertain AI predictions. Empty today because no model runs. |
| **Collections** | collector, operator, manager, administrator | The task list. Managers create and assign; collectors start and complete. |
| **Routes** | collector, manager, administrator | Route plans. Order tasks into a stop sequence from a depot. Honest: straight-line distance, no traffic, not navigation. |
| **Forecasting** | manager, administrator | Weekly volume forecast. Shows the backtest against a naive baseline next to the forecast. |
| **Anomalies** | manager, administrator | "Scan a series" finds unusual weeks and raises alerts. |
| **Incidents** | citizen, collector, manager, administrator | Residents report issues; managers triage and resolve them. |
| **Alerts** | everyone | Your notifications (collection, report, incident, anomaly, reward, system). Mark as read. |
| **Vehicles** | collector, manager, administrator | Fleet list, status, capacity, home depot, last position. |
| **Facilities** | everyone | Depots, processing centres, transfer stations and drop-off points, with capacity and coordinates. |
| **Zones** | everyone | Named service areas and their facilities. No map boundaries are drawn because none exist. |
| **Marketplace** | everyone | Surplus material listings (kg or units), requests, accept or decline, hand-over, expiry and renewal, photos. |
| **Reports** | citizens (create/own), staff (all) | Waste reports. |
| **Guide** | everyone | The sorting guide: materials, disposal methods and instructions with sources. Managers add categories and guidance. |
| **Rewards** | citizen (own), manager and administrator (staff). Collectors and operators have no Rewards item. | Citizens: balance, ledger, redeem. Staff: ledger, reward items, redemption queue, adjust points. |
| **Help assistant** | everyone | Ask a question; it answers from help articles or your own records, or says it has no answer. |
| **Support** | everyone (staff manage) | Support requests, assistant usage and help articles. |
| **Recovery** | operator, manager, administrator | Material recovery records and the verified recovery rate. |
| **Traceability** | operator, manager, administrator | Material passports and custody events. |
| **Settings → Users** | manager (view), administrator (change) | User list, roles with a required reason, deactivate/reactivate, reset two-step verification. |
| **Settings → Audit** | administrator | The log of who did what and when. |
| **Account menu** | everyone | System status, light/dark theme, sign out. **Security** page: two-step verification and password change. |

There is deliberately **no** "Smart Bins & Telemetry" menu item: the project has no real sensor data, and it will not show simulated sensors as if real.

Public pages (no sign-in): the landing page `/`, sign in, sign up, forgot password, reset password, verify e-mail.

## 6. The artificial intelligence parts

All AI work is separate from the web server code, uses only licence-checked data, and reports measured results rather than hopes.

**6.1 Photo classifier (not usable yet).** It would label a photo as plastic, paper, cardboard, glass, metal or "other waste" (only these six). A candidate model scored 86.7% accuracy on its own held-out photos from the TrashNet dataset (a tidy, studio-style photo set), but only 45.4% on a different public dataset, which shows it would not cope with real street photos. So it is a **candidate, not approved, and the file is not even in the repository**. The screen says so. Photos it is unsure about go to a human review queue. More data could not be used because the licences forbid it (RealWaste is non-commercial, TrashBox has no licence, and TACO yielded no usable images).

**6.2 Forecasting.** Statistical methods (such as Holt-Winters) predict weekly volume. Every forecast is tested by pretending the future is unknown (a *backtest*) and compared with the simplest guess (same as last week). Only series where the method beats the simple guess are described as better. It is trained on public city data (Austin, Ballarat) because the platform has no history yet.

**6.3 Anomaly detection.** Flags weeks that differ strongly from their normal pattern. Alerts are labelled "Public reference data" or "Platform data".

**6.4 Help assistant.** It is **not a chatbot that writes text**. It looks up 31 prepared help articles with database search and reads your own points, reports and requests. If it cannot find an answer it says so and offers a support request. It uses no outside language model. A language-model version would need an owner decision, a provider and a key.

## 7. How it is built (technology without jargon)

| Piece | Technology | What that means |
|---|---|---|
| What you see in the browser | **React 19, TypeScript, Vite** | The screens. TypeScript catches mistakes before they run. |
| The server | **FastAPI (Python)** | Receives requests, checks who you are, applies rules, talks to the database. |
| The database | **PostgreSQL 16** with **SQLAlchemy** and **Alembic** | Stores everything. Alembic keeps a numbered history of every change to the table structure. |
| Packaging | **Docker and Docker Compose** | Starts the whole system with one command. |
| Automatic checking | **GitHub Actions** | On every change, runs tests, style checks and security scans. |
| Maps | **MapLibre** (offline), optional **Google Maps**, optional **OSRM** | Draw places and routes. |
| AI | A pretrained image feature extractor (TFLite) plus a small logistic-regression layer; forecasting and anomaly code in numpy and scikit-learn | Kept in the `ml/` folder, apart from the server. No PyTorch or TensorFlow is used at run time. |

**Modular monolith.** The server is one program, divided into 22 labelled modules (users, auth, waste reports, collection, fleet…). Each module has its own routes, rules and storage code and may use another only through its public interface. It was chosen over many small services because one team can build, test and run it far more simply (see `docs/decisions/ADR-0001-modular-monolith.md`). There is no Redis, message queue, Kubernetes or PostGIS.

**One front door for the browser.** All browser requests to the server go through one function (`apiRequest`), which adds sign-in tokens and handles errors the same way everywhere. Server errors always have the same shape: a code, a message, details and a request ID you can quote when reporting a problem.

**How a request travels.** Browser → (web server) → FastAPI route → permission check → rules → database → response. Important actions also write an **audit log** entry.

## 8. A tour of the folders

| Folder | What is in it |
|---|---|
| `backend/` | The server. `app/modules/<name>/` holds each of the 22 modules. `migrations/versions/` holds database changes 0001–0016. `tests/` holds 60 test files. |
| `frontend/` | The web app. `src/features/<name>/` holds each screen group. `src/app/router.tsx` lists every page address. `src/components/navigation/nav-items.ts` builds the sidebar. `tests/` holds 37 test files. |
| `ml/` | Training and evaluation code, the model registry entry, git-ignored `artifacts/` (model files, absent). |
| `datasets/manifests/` | Records of which data sources were checked and why each was or was not used. No raw data is committed. |
| `deployment/docker/` and `compose.yaml` | Container recipes and the one-command start-up. |
| `docs/` | All documentation (see part 14). |
| `tests/` | `e2e/` browser tests, `contract/` API shape tests, `smoke/` quick live check. |
| `scripts/` | Helper scripts: quality checks, database generators, security audits, demo data, map assets, setup. |
| `.github/workflows/` | The automatic checks. |
| `Makefile` | Short commands such as `make up`, `make test`. |

## 9. The database

PostgreSQL holds **46 tables**: users, roles, permissions and sessions; waste reports and their photos; classification predictions and reviews; tasks, events and status history; vehicles and location events; route plans and stops; facilities and zones; recovery records; passports and custody events; incidents; marketplace listings, photos and requests; reward ledger, items and redemptions; notifications; forecasts and anomaly alerts; support tickets, help articles and assistant messages; audit logs. There are 94 foreign keys, 114 validation rules and 205 indexes. Money-like values (weights, points) are stored exactly, not as rough decimals. The ledger of points is **append-only**: mistakes are fixed with a reversal or adjustment entry, never by editing history.

Documents: `docs/database/data-dictionary.md` (every table and column), `er-diagram.md`, `schema-overview.md`. Both are generated from the code and checked automatically so they cannot drift.

Migrations were verified to apply from nothing, to produce no drift, and to roll back to empty and apply again.

## 10. Security

- **Passwords** are stored with Argon2id. Minimum 12 characters; common or personal passwords are refused. Five wrong tries on one e-mail lock it for 15 minutes.
- **Sessions:** a short-lived access token plus a refresh token in an HttpOnly cookie that needs a special header (protection against forged requests). Changing your password signs out your other devices.
- **Two-step verification** (an authenticator app, with recovery codes). Optional by default. When `ENVIRONMENT=production`, administrators and managers **must** set it up, and the server blocks everything else until they do.
- **Deny by default:** every route needs a permission unless it is on a short public list, and a test fails if a new route forgets one.
- **Audit log:** role changes, deactivations and other sensitive actions are recorded with who, when and why.
- **Privacy:** reporter identity and private addresses are not shown on maps. Photos are checked and stripped of hidden location data before storage.
- **Scans:** dependency audits, static analysis and secret scans run in CI and were clean at the audit.
- **Secrets** (keys, passwords) live in environment variables, never in the repository. The server-only Google key can never reach the browser.

Read `SECURITY.md` and `docs/security/` for more.

## 11. How to run it

You need **Docker** and **make** (easiest), or Python 3.11+ and Node 22 for the manual route. The commands below come from the project's `Makefile` and README.

**Option A — everything in containers**
```
make env          # creates a .env file from the template
make up           # builds and starts database, server and web app
```
Open `http://localhost:5173`. Sign up on the page, then make that account an administrator:
```
docker compose exec -e ECOMIND_ADMIN_PASSWORD='choose-a-long-password' backend python -m app.cli create-admin --email you@example.org --name "Your Name"
docker compose exec backend python -m app.cli seed-support-knowledge
```
(The first command creates or promotes the account; the second loads the 31 help articles.) Other useful addresses: API documentation `http://localhost:8000/api/v1/docs` (local mode only), health `http://localhost:8000/health`, readiness `/ready`.

**Option B — without Docker:** `make setup`, `make db-up`, `make migrate`, `make backend-dev`, `make frontend-dev`.

**Checks:** `make check` (style and types), `make test`, `make test-e2e`. Quick live check: `python3 tests/smoke/smoke.py --api http://localhost:8000 --web http://localhost:5173`.

**E-mail in local mode:** the "console" backend prints verification and reset links in the server log (`docker compose logs backend`). Nothing is sent. For real e-mail, an SMTP setting is required.

**Demo data (optional):** `scripts/demo/seed_demo.py` fills a *throw-away* local database with invented, labelled records through the real API. Reference series come from `python -m app.cli import-reference-series --key austin` (needs a local clone of the public dataset).

**Never** put real passwords or keys in files you commit.

## 12. Honest status

**Works and is tested:** accounts and five roles; all workflow screens in part 5; forecasting and anomaly scans on public data; help assistant; offline map without tiles; password reset and e-mail verification (with the console e-mail); two-step verification and its enforcement rules; audit log; system status; light and dark themes.

**Not working or not proven:**
- **No approved AI classifier.** (Part 6.1.)
- **Never deployed.** No server, domain, TLS, backups or monitoring.
- **No map tile file**, so maps show a plain background and a notice.
- **Google Maps/Routes, OSRM, real GPS and real e-mail** were never tried with real services.
- A collector who is assigned an incident cannot open it (decision pending).
- No human accessibility review; automated checks only.
- Backend tests: 763 passed, 1 skipped. Browser tests: 31 passed, 1 skipped. Frontend tests: 365 passed.

The full list is in `docs/project-completion/PROJECT_AUDIT_REPORT.md` and `LIMITATIONS.md`.

## 13. Glossary

- **API** — the set of addresses the browser (or another program) uses to ask the server to do things.
- **Audit log** — a permanent record of sensitive actions.
- **Backtest** — testing a forecast against history it was not shown.
- **CI** — automatic checking that runs on every change in GitHub.
- **Container / Docker** — a sealed package of a program and what it needs to run.
- **CSRF** — a trick where another website makes your browser act for you; the special header blocks it.
- **Endpoint** — one address on the API, for example "list facilities".
- **Foreign key** — a database link that forces a row to refer to something that exists.
- **JWT / access token** — a short-lived proof that you are signed in.
- **Ledger** — a list of entries that is only ever added to.
- **Migration** — a numbered, replayable change to the database structure.
- **MFA / two-step verification / TOTP** — a six-digit code from an app, required in addition to the password.
- **Modular monolith** — one program organised into clearly separated modules.
- **PMTiles** — a single file holding map tiles for an area.
- **RBAC** — role-based access control: what you may do depends on your roles.
- **Retrieval-only assistant** — finds existing text; does not write new answers.
- **Seed** — loading starting data into an empty database.
- **Tile** — a small square piece of a map image.

## 14. Where to read more

- Audit and status: `docs/project-completion/PROJECT_AUDIT_REPORT.md`
- Test it yourself: `docs/testing/MANUAL_TEST_GUIDE.md`
- Architecture: `docs/architecture/`, decisions `docs/decisions/` (ADR-0001 to 0003)
- API: `docs/api/` (one file per module) and `docs/security/route-permission-matrix.md`
- Database: `docs/database/`
- AI: `docs/ml/` (model cards, evaluation protocol, dataset research, support assistant)
- Maps: `docs/maps/`
- Operations: `docs/operations/` (runbook, troubleshooting, account recovery, backup and rollback)
- Requirements and scope: `docs/requirements/`
- Academic material: `docs/academic/` (abstract, objectives, methodology, results, user manual, viva outline)
- Screens against the 22 reference designs: `docs/project-completion/SCREEN_TRACEABILITY.md`
- Known limits: `docs/project-completion/LIMITATIONS.md`; open decisions: `DECISION_LOG.md`
