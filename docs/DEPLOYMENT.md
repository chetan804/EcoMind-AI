# Deployment guide

## Reference deployment (Docker Compose)

```bash
cp backend/.env.example backend/.env
# REQUIRED EDITS in backend/.env:
#   ECOMIND_SECRET_KEY=<python -c "import secrets;print(secrets.token_urlsafe(48))">
# ALSO set in the shell (used by compose for the DB password):
#   export POSTGRES_PASSWORD=<strong password>

docker compose up --build -d
```

- Frontend: `http://localhost:8080` (nginx serves the SPA and reverse-proxies
  `/api`, `/docs`, `/openapi.json` to the API container — same-origin, no CORS).
- API container runs Alembic migrations on boot, then uvicorn.
- Named volumes: `pgdata` (database), `uploads` (media objects).

### Services

| Service | Image | Notes |
| --- | --- | --- |
| `db` | postgres:16-alpine | health-checked; api waits for readiness |
| `api` | built from `backend/Dockerfile` | non-root user, `/health` healthcheck, embedded job worker |
| `web` | built from `frontend/Dockerfile` | nginx, security headers, immutable asset caching |

## Configuration reference

Every setting is env-driven (prefix `ECOMIND_`); see `backend/.env.example` for the
annotated list. The critical ones:

| Variable | Production requirement |
| --- | --- |
| `ECOMIND_ENVIRONMENT` | `production` |
| `ECOMIND_SECRET_KEY` | **Required** — app refuses to boot without it |
| `ECOMIND_DATABASE_URL` | TCP asyncpg URL (e.g. `postgresql+asyncpg://ecomind:…@db:5432/ecomind`) |
| `ECOMIND_CORS_ORIGINS` | Exact origins (only needed if the API is called cross-origin; same-origin nginx deployments don't need it) |
| `ECOMIND_OSRM_BASE_URL` | Optional — real road geometry when set |
| `ECOMIND_AI_DEFAULT_PROVIDER` + provider key | Optional — without a key, AI runs the labelled heuristic baseline |

Secrets belong in the environment / secret manager — never in the repo (`.env` is
gitignored; only `.env.example` is committed).

## Production checklist

- [ ] `ECOMIND_ENVIRONMENT=production`, strong `ECOMIND_SECRET_KEY` (48+ random bytes)
- [ ] TLS termination in front of nginx (or at the load balancer); HSTS enabled there
- [ ] `POSTGRES_PASSWORD` strong; DB not exposed publicly; automated backups (see OPERATIONS)
- [ ] Object storage: mount persistent volume at `/srv/app/data` (or adapt
      `core/storage.py` to your S3-compatible backend)
- [ ] Set `ECOMIND_CORS_ORIGINS` if the API is consumed from other origins
- [ ] Decide AI provider: configure a key, or run the labelled heuristic baseline
- [ ] Optional: OSRM endpoint for real road geometry
- [ ] Seed a first admin: register → create org (you become org admin), or use
      `seed_demo.py` for a labelled demo environment

## Scaling notes

- **Vertical-first**: a single API container with the embedded worker comfortably
  serves small/medium municipalities.
- **Split the worker**: run a second deployment of the same image with
  `ECOMIND_RUN_EMBEDDED_WORKER=true` and set it `false` on the web-facing instances —
  jobs are claimed via `SELECT … FOR UPDATE SKIP LOCKED`, so multiple workers are safe.
- **Stateless API**: all state lives in PostgreSQL + object storage; scale horizontally
  behind any load balancer with sticky-free routing.
- **Database**: managed PostgreSQL (RDS/Cloud SQL) recommended; the app needs no
  exotic extensions.

## Health & monitoring endpoints

- `GET /health` — liveness (used by Docker healthchecks)
- `GET /api/v1/admin/platform/overview` — cross-org stats (platform admin JWT)
- Structured JSON logs with `request_id` on every line — ship to any log aggregator.

## Rollbacks

Images are immutable; roll back by redeploying the previous image tag. Alembic
migrations are forward-only in this release — before upgrading, back up the database
(`pg_dump`) and test the migration path on a staging copy.
