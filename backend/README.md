# Backend

FastAPI modular monolith exposing the REST API under `/api/v1` (plus `/health` and `/ready`). Architecture rules: `docs/architecture/component-boundaries.md`. API rules: `docs/api/api-conventions.md`.

**State:** application factory, validated configuration, structured errors, request ids, security primitives, health/readiness, complete initial schema and migration. **No module has routes yet**; module READMEs state each module's status.

## Layout
| Path | Responsibility |
|---|---|
| `app/main.py` | `create_app()` factory (run with `uvicorn app.main:create_app --factory`) |
| `app/api/` | `router.py` mounts versions; `v1/router.py` registers module routers |
| `app/core/` | `config` (settings, startup validation), `security` (Argon2id, JWT, refresh tokens), `logging`, `exceptions` (error envelope), `middleware` (request id, access log), `permissions` |
| `app/db/` | `base` (declarative base, naming convention, mixins, `enum_column`), `session` (engine/session), `metadata` (explicit model registration for Alembic) |
| `app/common/` | `pagination`, `enums`, `response_schemas`, `time` |
| `app/modules/<name>/` | business modules (see each README) |
| `app/integrations/` | adapters: `file_storage`, `mapping`, `email`, `sensors` (boundaries only) |
| `app/health/` | `/health`, `/ready` |
| `migrations/` | Alembic environment and versions (`0001` initial schema) |
| `tests/` | `unit`, `api`, `security`, `integration`, `fixtures` |

## Run
```bash
make setup && make db-up && make migrate && make backend-dev     # from the repository root
```
Configuration is read from environment variables (`backend/.env.example` documents every variable); missing or invalid values stop the process at startup.

## Quality
```bash
cd backend
../backend/.venv/bin/ruff check . && ../backend/.venv/bin/ruff format --check . && ../backend/.venv/bin/mypy
TEST_DATABASE_URL=postgresql+psycopg://USER:PASS@localhost:5432/postgres ../backend/.venv/bin/pytest
```
(or `make lint typecheck test-backend` from the root). Database tests create and drop their own isolated databases. See `docs/testing/testing-strategy.md`.

## Adding a module
1. Create only the files needed from the module contract in `app/modules/<name>/`.
2. Models in `models.py`, imported in `app/db/metadata.py`; `make migration m="..."`, review, add constraint tests, `make data-dictionary`.
3. Register the router in `app/api/v1/router.py`; add API + security tests; update the module README, requirements status and API docs.
