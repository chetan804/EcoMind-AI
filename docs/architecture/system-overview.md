# System overview

EcoMind AI is a waste-intelligence, waste-management-operations and circular-economy platform. This document describes what the repository **contains** (status as of 2026-10-22); anything not built is named in [LIMITATIONS.md](../project-completion/LIMITATIONS.md), not here.

## Components

```
Browser ──HTTPS──> Frontend (React SPA, static files; offline map tiles from /map-data)
   │
   └──HTTPS /api/v1──> Backend (FastAPI modular monolith) ──SQL──> PostgreSQL
                            │  ├── file storage (local volume; interface in integrations/file_storage)
                            │  ├── e-mail (integrations/email: console, SMTP; Mailpit for local and CI tests)
                            │  ├── mapping (integrations/mapping: optional OSRM or Google Routes, off by default)
                            │  ├── sensors (integrations/sensors: boundary only, no hardware, not in navigation)
                            │  └── classifier inference (ml/…, loaded from MODEL_ARTIFACTS_DIR; none is shipped or active)
                            └── /health, /ready (operational, unversioned)
```

| Component | Directory | Technology | State |
|---|---|---|---|
| Frontend | `frontend/` | React 19, TypeScript, Vite, React Router, TanStack Query, React Hook Form + Zod, MapLibre + PMTiles (Google Maps optional) | 26 feature folders; every reference screen except the two smart-bin/telemetry ones, plus the help assistant, support desk, tracking and maps |
| Backend | `backend/` | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3 | 22 business modules, 168 operations under `/api/v1` plus `/health` and `/ready` |
| ML | `ml/` | Python, NumPy, Pillow, LiteRT (TFLite) for serving; scikit-learn for training only | one candidate material classifier (not activated), statistical forecasting and anomaly algorithms in `ml/time_series` |
| Database | PostgreSQL 16 | | 46 tables, 17 Alembic migrations (head `0017`) |
| Local infra | `compose.yaml`, `deployment/` | Docker Compose | `db`, `migrate`, `backend`, `frontend`; optional profiles `demo-mail` (Mailpit) and `osrm` |

## Decisions established in the foundation (still in force)

Locked by the project specification: React/TypeScript/Vite, React Router, FastAPI, REST under `/api/v1`, Pydantic, PostgreSQL, SQLAlchemy 2.x, Alembic, pytest, Vitest + React Testing Library, Playwright, Docker Compose, GitHub Actions, modular monolith (ADR-0001).

Choices made while establishing the foundation (changing them requires an ADR):

| Decision | Choice | Reason |
|---|---|---|
| DB access | Synchronous SQLAlchemy 2 + psycopg 3 | Simpler transactions and testing; FastAPI runs sync endpoints in a thread pool. Revisit only for measured I/O bottlenecks. |
| Primary keys | UUIDs from `gen_random_uuid()` | Safe to expose in URLs; no enumeration. |
| Enum storage | `VARCHAR` + named `CHECK` (`ck_<table>_<col>_valid`) | Adding a value is a plain constraint change, not a PostgreSQL ENUM type alteration. |
| Geography | `latitude`/`longitude` numeric columns with range checks | PostGIS is not justified by any current requirement. |
| Auth | Argon2id passwords; short-lived JWT access token + rotating opaque refresh token (HttpOnly cookie, hashed in `auth_sessions`) | See `docs/security/security-baseline.md`. Implemented, with optional TOTP two-step verification (required for administrators and managers in production). |
| App construction | `create_app()` factory, no module-level app | Importing the package never requires a valid environment; tests inject settings. |
| Frontend styling | Plain CSS with design tokens (`styles/global.css`) | No UI framework; avoids an unrequested dependency. See `docs/ui/design-system.md`. |
| Frontend API origin | `VITE_API_BASE_URL` (empty = same origin via dev/preview proxy) | One configuration point; no hardcoded URLs. |
| Python versions | CI tests 3.11 and 3.12; images use 3.12 | |
| Node | 22.22+ | Required by React Router 8. |

## What is deliberately absent
Redis, Celery or any message broker, Kubernetes, Supabase, microservices, PostGIS, sensor/IoT tables, a built-in scheduler (periodic jobs are CLI commands the operator schedules) and a generative-language-model provider. Each is added only when a documented requirement justifies it (see `docs/project-roadmap.md`). Mapping and e-mail providers were added as adapters: offline OpenStreetMap tiles by default, optional OSRM or Google, console or SMTP e-mail (`docs/maps/`, ADR-0002).

## Related documents
`component-boundaries.md` (module ownership and dependency rules), `data-flow.md`, `deployment-architecture.md`, `../decisions/ADR-0001-modular-monolith.md`.
