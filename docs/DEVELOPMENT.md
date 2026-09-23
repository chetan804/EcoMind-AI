# Development guide

## Prerequisites

- Python 3.11+ (3.12 recommended)
- Node 20+ (22 recommended)
- No system PostgreSQL required — the repo bundles a dev Postgres via `pgserver`
  (data lives in `.pgdata/`, gitignored).

## Setup

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"

cp .env.example .env            # set ECOMIND_SECRET_KEY for stable dev tokens

./venv/bin/python scripts/dev_pg.py &     # bundled PostgreSQL (idempotent)
./venv/bin/alembic upgrade head
./venv/bin/uvicorn app.main:app --reload  # http://localhost:8000 · /docs
```

Frontend:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 — proxies /api, /docs to :8000
```

Useful scripts:

```bash
./venv/bin/python scripts/seed_demo.py --reset   # re-seed the demo org (destructive)
./venv/bin/python scripts/dev_pg.py              # boot/reuse bundled Postgres
```

## Configuration

All settings come from the environment (prefix `ECOMIND_`) or `backend/.env` —
see `backend/.env.example` for the full annotated reference. Production refuses to
boot without `ECOMIND_SECRET_KEY`.

## Testing

```bash
cd backend
./venv/bin/pytest -q                     # full suite (real Postgres, real migrations)
./venv/bin/pytest tests/test_tenant_isolation.py -q   # the release-blocking suite
./venv/bin/ruff check app tests scripts

cd frontend
npm run typecheck
npm test                                 # vitest
npm run build
```

Backend tests create an isolated `ecomind_test_*` database per session (bundled
pgserver, or `ECOMIND_TEST_DATABASE_URL` in CI with a Postgres service) and run the
real Alembic migrations — no mocked database layer.

## Conventions

**Backend**
- One domain per `app/<domain>/` package: `models.py`, `router.py`, `service.py`,
  `schemas.py`. Routers stay thin; logic lives in services.
- Every tenant query filters by `organization_id` from `AuthCtx` — never trust
  client-supplied ids for scoping.
- Mutations that matter get an audit entry (`app.audit.service.record`).
- Errors: raise typed errors from `app.core.errors` (mapped to structured JSON).
- Async all the way: async SQLAlchemy sessions; no blocking calls in handlers.

**Frontend**
- TypeScript strict; components small and composable; design-system primitives in
  `src/ui.tsx`, map in `src/map.tsx`.
- All server access via `src/lib/api.ts` (typed `get/post/patch/postForm`) — never
  `fetch` directly in components.
- Server state belongs to TanStack Query; local UI state to `useState`.
- Anything simulated or demo-related must render a `SimBadge` / `DemoBadge`.
- Relative API URLs only (`/api/v1/...`) — the dev proxy / nginx handles origins.

## Seeding & demo data

`seed_demo.py --reset` deletes the demo organization (FK cascade) and rebuilds:
org + zones + points + vehicles + staff/citizens + 14 simulated devices + 5 days of
simulated telemetry + reports/complaints/collections/routes/notifications/rewards,
then runs the sustainability recompute. All synthetic rows carry `is_simulated` /
`is_demo` flags. The script is idempotent via `--reset` and safe to point at a dev
database only.

## Adding a domain (checklist)

1. Models in `app/<domain>/models.py` (inherit `TenantScoped` if org-owned).
2. Alembic revision: `./venv/bin/alembic revision --autogenerate -m "…"` then review.
3. Schemas (Pydantic v2, `*Out` for responses, `*In` for requests).
4. Service functions taking `organization_id` explicitly.
5. Router with permission dependencies.
6. Tests — include a cross-tenant case in `tests/test_tenant_isolation.py` style.
7. Audit entries on mutations; frontend page + types; docs update.

## Repo layout

```
backend/    FastAPI app, Alembic migrations, scripts, tests
frontend/   React SPA (Vite + Tailwind v4 + TanStack Query)
docs/       Product/architecture/ops documentation + ADRs
docker-compose.yml, backend/Dockerfile, frontend/Dockerfile
.github/workflows/ci.yml
```
