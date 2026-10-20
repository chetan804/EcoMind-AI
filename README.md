# EcoMind AI

An AI-powered waste-intelligence, waste-management-operations and circular-economy platform.

> **Project state.** The backend (19 modules under `/api/v1`), the web app (every reference screen except the planned Marketplace, Locations and Zones, and the excluded smart-bin telemetry) and the CI are built and tested. The only trained model is a **candidate** waste classifier (TrashNet, six classes, held-out accuracy 0.867) and **no model is active by default**: classification says so instead of guessing. Forecasts and anomaly flags use classical statistical methods with a naive baseline, and label public reference data as such. Rewards and impact figures come from recorded collections only. Exact status, evidence, losses and open work: [`docs/project-completion/IMPLEMENTATION_STATUS.md`](docs/project-completion/IMPLEMENTATION_STATUS.md); screens: [`docs/ui/screen-inventory.md`](docs/ui/screen-inventory.md).

## What it does
Citizens report waste with a photo and get sorting guidance; managers review reports, plan and assign collections (vehicles, deterministic route ordering), record collected weights; facility operators record material recovery and chain-of-custody passports; rewards and executive analytics are computed from the database; community incidents are triaged; administrators manage users, roles and MFA and read the audit log.

## Stack
React 19 + TypeScript + Vite (React Router, TanStack Query, React Hook Form + Zod) · FastAPI + Pydantic v2 · PostgreSQL 16 · SQLAlchemy 2 + Alembic · pytest · Vitest + React Testing Library · Playwright · Docker Compose · GitHub Actions. Backend is a **modular monolith** ([ADR-0001](docs/decisions/ADR-0001-modular-monolith.md)).

## Repository layout
| Directory | Responsibility |
|---|---|
| [`frontend/`](frontend/README.md) | React SPA. Feature folders under `src/features/`, shared UI under `src/components/`. |
| [`backend/`](backend/README.md) | FastAPI app: `app/modules/<domain>` (business modules), `core/`, `db/`, `common/`, `integrations/`, `health/`; Alembic in `migrations/`. |
| [`ml/`](ml/README.md) | Training, evaluation and inference code, separate from the API. |
| [`datasets/`](datasets/README.md) | Dataset descriptions (manifests). Data files are git-ignored. |
| [`deployment/`](deployment/README.md) | Dockerfiles for independent frontend/backend deployment. |
| [`tests/`](tests/README.md) | Cross-application tests: end-to-end, API contract, smoke. |
| [`scripts/`](scripts/README.md) | Setup and quality helper scripts. |
| [`docs/`](docs/) | Architecture, decisions, requirements, API, database, ML, security, testing, UI, operations, roadmap. |
| `.github/workflows/` | CI: `backend-ci`, `frontend-ci`, `quality-gates`. |

Start with [`docs/architecture/system-overview.md`](docs/architecture/system-overview.md) and [`docs/architecture/component-boundaries.md`](docs/architecture/component-boundaries.md).

## Local setup

Prerequisites: Git, GNU Make, Python 3.11 or 3.12, Node.js 22.22+ (with npm), and Docker with Compose v2.

### Option A — everything in containers
```bash
git clone https://github.com/chetan804/EcoMind-AI.git
cd EcoMind-AI
make env     # creates .env files from the templates and generates local secrets (never overwrites)
make up      # db -> migrations -> backend -> frontend, waits until healthy
```
- App: http://localhost:5173 (landing page; register at `/sign-up`, create the first administrator with `python -m app.cli create-admin`; see `backend/README.md`)
- API docs: http://localhost:8000/api/v1/docs · liveness `GET /health` · readiness `GET /ready`
- Stop: `make down` (keeps the database volume) · Logs: `make logs`

### Option B — run backend and frontend on the host
```bash
git clone https://github.com/chetan804/EcoMind-AI.git
cd EcoMind-AI
make setup       # .env files, backend/.venv with dev tools, frontend dependencies
make db-up       # PostgreSQL in Docker (or point backend/.env at your own PostgreSQL)
make migrate     # apply Alembic migrations
make backend-dev     # terminal 1 -> http://localhost:8000
make frontend-dev    # terminal 2 -> http://localhost:5173
```

### Verify
```bash
make check lint typecheck test      # structure/secret checks, linters, type checks, backend (needs DB), frontend, ML, contract tests
python3 tests/smoke/smoke.py --api http://localhost:8000 --web http://localhost:5173
make install-e2e && make test-e2e   # browser tests against the running stack
```
`make help` lists every command. More detail, migrations workflow and deployment outline: [`docs/operations/runbook.md`](docs/operations/runbook.md); problems: [`docs/operations/troubleshooting.md`](docs/operations/troubleshooting.md).

## Conventions every feature must follow
1. **Boundaries:** backend features are modules following the contract in `component-boundaries.md`; frontend features follow `src/features/<name>/` with a public `index.ts`. Do not add application roots or rename canonical directories without an ADR.
2. **API:** everything under `/api/v1`, typed Pydantic schemas, pagination, structured errors, authorization ([`docs/api/api-conventions.md`](docs/api/api-conventions.md)).
3. **Database:** models live in the owning module; schema changes only through reviewed Alembic migrations; constraints for invariants; units in column names ([`docs/database/schema-overview.md`](docs/database/schema-overview.md)).
4. **Security:** server-side validation and authorization, no secrets in code or bundles ([`docs/security/security-baseline.md`](docs/security/security-baseline.md)).
5. **ML:** no model is claimed without evidence ([`docs/ml/evaluation-protocol.md`](docs/ml/evaluation-protocol.md)).
6. **Tests:** every feature ships with tests at the right layers ([`docs/testing/testing-strategy.md`](docs/testing/testing-strategy.md)); never weaken a test to pass.
7. **No fake data:** no mock arrays, simulated predictions or placeholder dashboards as production behaviour. No Smart Bins/telemetry navigation; sensors stay an internal adapter boundary.

Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md) · Security policy: [`SECURITY.md`](SECURITY.md) · License: [`LICENSE`](LICENSE)
