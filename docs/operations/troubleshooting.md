# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Backend exits at startup with `ValidationError ... database_url / secret_key` | Missing or invalid environment | Run `make env`; check `backend/.env`; `SECRET_KEY` needs ≥ 32 chars and must not contain the template placeholder. |
| `SECRET_KEY still contains the example placeholder` | Copied `.env.example` by hand | `make env` (generates secrets) or set a value from `python -c "import secrets;print(secrets.token_urlsafe(48))"`. |
| `/ready` → 503 `database unreachable` | PostgreSQL not running, wrong host/port/password | `docker compose ps`; with host-based dev the URL host is `localhost`, inside Compose it is `db`. |
| `/ready` → 503 `schema revision is none, expected …` | Migrations not applied | `make migrate` (Compose does it automatically via the `migrate` service). |
| `/ready` → `schema revision is X, expected Y` | Database behind (or ahead of) the code | Upgrade with `make migrate`; if ahead, you are running older code than the database. |
| `docker compose` complains `set POSTGRES_PASSWORD in .env` | No `.env` | `make env`. |
| Compose `migrate` service fails | Database not healthy yet or bad credentials | `docker compose logs migrate db`. If you changed `POSTGRES_PASSWORD` after the volume was created, the old password persists in the volume: restore the old value in `.env` (or deliberately recreate the volume only if you accept losing development data). |
| Frontend shows "Unreachable" on System status | Backend down or proxy target wrong | Check `DEV_PROXY_TARGET`; in Compose it must be `http://backend:8000`. With a separate frontend origin set `VITE_API_BASE_URL` and add the origin to `CORS_ALLOWED_ORIGINS`. |
| Browser CORS error | Frontend origin missing from backend CORS | Add it to `CORS_ALLOWED_ORIGINS` (comma separated) and restart the backend. |
| Vite shows "Blocked request. This host is not allowed" | Accessing the dev server through another hostname (tunnel, preview URL) | Add it to `DEV_ALLOWED_HOSTS`. |
| `alembic revision --autogenerate` creates an empty/odd migration | Models not imported or DB not at head | Register the module in `app/db/metadata.py`; run `make migrate` first. |
| Alembic autogenerate shows duplicate `CheckConstraint` for enums | Used `sqlalchemy.Enum(create_constraint=True)` directly | Use `enum_column()` from `app/db/base.py`. |
| Integration tests are skipped | `TEST_DATABASE_URL` not set | Set it to a server URL whose role can `CREATE DATABASE`. |
| `permission denied to create database` in tests | Role lacks CREATEDB | Use a superuser/owner role for tests (the Compose user is the PostgreSQL superuser). |
| `ModuleNotFoundError: app` when running pytest | Wrong working directory | Run from `backend/` (or `make test-backend`). |
| ESLint: "Import a feature only through its public index.ts" | Deep import into a feature | Export it from the feature's `index.ts` or move shared code to `components/`/`lib/`. |
| `npm ci` fails with engine error | Node older than 22.22 | Install Node 22.22+ (React Router 8 requirement). |
| Playwright cannot find a browser | Browsers not installed | `make install-e2e` (or set `E2E_CHROMIUM_PATH`). |
| `make test-backend` cannot connect with an empty password | `.env` missing | `make env`, or pass `TEST_DATABASE_URL=...` explicitly. |
