# Deployment architecture

Frontend and backend are **independently deployable**. Nothing in the repository claims that a production environment exists.

## Local development (implemented)
`compose.yaml`: `db` (PostgreSQL 16, named volume `ecomind_pgdata`, health check) → `migrate` (one-shot `alembic upgrade head`) → `backend` (uvicorn, health check on `/ready`, volume `ecomind_storage` for uploads) → `frontend` (Vite dev server proxying `/api`, `/health`, `/ready` to `backend`). Ports: 5173 (frontend), 8000 (backend), 5432 (database, bound to 127.0.0.1).

## Target topology
```
 users ──> static hosting / CDN / nginx (frontend image, port 8080)
 users ──> HTTPS reverse proxy / platform ingress ──> backend container(s) ──> managed PostgreSQL
                                                         └──> persistent file storage
```
Requirements any target platform must meet:
- **Frontend:** serve the static build with SPA fallback; build with `VITE_API_BASE_URL` set to the public backend origin; that origin must be listed in the backend's `CORS_ALLOWED_ORIGINS`.
- **Backend:** run the image with environment variables (`backend/.env.example` documents all); `ENVIRONMENT=production` enforces strong `SECRET_KEY`, secure cookies and explicit CORS origins at startup and disables OpenAPI docs. Terminate TLS in front. Use `/health` for liveness and `/ready` for readiness probes.
- **Migrations:** run `alembic upgrade head` as a separate release step *before* routing traffic to the new version (never on every container start). Migrations must be backward compatible with the previous app version for zero-downtime releases (add before use, remove after).
- **Database:** PostgreSQL 14+ (uses `gen_random_uuid()`), automated backups and tested restores.
- **File storage:** a persistent volume or (future adapter) object storage; uploads are lost if the backend runs on ephemeral disk.
- **Model artifacts:** a read-only volume or download step populating `MODEL_ARTIFACTS_DIR`.
- **Secrets:** from the platform's secret store, never from the repository or the frontend bundle.

## Single backend instance assumption
The backend is stateless except for the local file-storage backend. Running multiple instances requires shared file storage (see integration). No cache, queue or scheduler exists; background work, if ever required, needs a documented requirement and an ADR before adding infrastructure.
