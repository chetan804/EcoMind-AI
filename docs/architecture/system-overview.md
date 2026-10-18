# System overview

EcoMind AI is a waste-intelligence, waste-management-operations and circular-economy platform. This document describes what the repository **contains today** and the architecture all future work extends. Items marked *planned* are not implemented.

## Components

```
Browser ──HTTPS──> Frontend (React SPA, static files)
   │                       
   └──HTTPS /api/v1──> Backend (FastAPI modular monolith) ──SQL──> PostgreSQL
                            │  ├── file storage (local volume; interface in integrations/file_storage)
                            │  └── ML inference code (ml/…, loaded from MODEL_ARTIFACTS_DIR)   [planned]
                            └── /health, /ready (operational, unversioned)
```

| Component | Directory | Technology | State |
|---|---|---|---|
| Frontend | `frontend/` | React 19, TypeScript, Vite, React Router, TanStack Query, React Hook Form + Zod | Shell + system-status page |
| Backend | `backend/` | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, psycopg 3 | App factory, config, security primitives, health/ready, schema + migration |
| ML | `ml/` | Python, Pillow now; scikit-learn and/or PyTorch per capability later | Image preprocessing only; no models |
| Database | PostgreSQL 16 | | Initial schema: 29 tables |
| Local infra | `compose.yaml`, `deployment/` | Docker Compose | db, migrate, backend, frontend |

## Decisions established in the foundation

Locked by the project specification: React/TypeScript/Vite, React Router, FastAPI, REST under `/api/v1`, Pydantic, PostgreSQL, SQLAlchemy 2.x, Alembic, pytest, Vitest + React Testing Library, Playwright, Docker Compose, GitHub Actions, modular monolith (ADR-0001).

Choices made while establishing the foundation (changing them requires an ADR):

| Decision | Choice | Reason |
|---|---|---|
| DB access | Synchronous SQLAlchemy 2 + psycopg 3 | Simpler transactions and testing; FastAPI runs sync endpoints in a thread pool. Revisit only for measured I/O bottlenecks. |
| Primary keys | UUIDs from `gen_random_uuid()` | Safe to expose in URLs; no enumeration. |
| Enum storage | `VARCHAR` + named `CHECK` (`ck_<table>_<col>_valid`) | Adding a value is a plain constraint change, not a PostgreSQL ENUM type alteration. |
| Geography | `latitude`/`longitude` numeric columns with range checks | PostGIS is not justified by any current requirement. |
| Auth | Argon2id passwords; short-lived JWT access token + rotating opaque refresh token (HttpOnly cookie, hashed in `auth_sessions`) | See `docs/security/security-baseline.md`. Primitives implemented; endpoints not yet. |
| App construction | `create_app()` factory, no module-level app | Importing the package never requires a valid environment; tests inject settings. |
| Frontend styling | Plain CSS with design tokens (`styles/global.css`) | No UI framework chosen yet; avoids an unrequested dependency. See `docs/ui/design-system.md`. |
| Frontend API origin | `VITE_API_BASE_URL` (empty = same origin via dev/preview proxy) | One configuration point; no hardcoded URLs. |
| Python versions | CI tests 3.11 and 3.12; images use 3.12 | |
| Node | 22.22+ | Required by React Router 8. |

## What is deliberately absent
Redis, Celery or any message broker, Kubernetes, Supabase, microservices, sensor/IoT tables, a mapping provider, an email provider. Each is added only when a documented requirement justifies it (see `docs/project-roadmap.md`).

## Related documents
`component-boundaries.md` (module ownership and dependency rules), `data-flow.md`, `deployment-architecture.md`, `../decisions/ADR-0001-modular-monolith.md`.
