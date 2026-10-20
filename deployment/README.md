# Deployment

Container build definitions for deploying the frontend and backend **independently**.

| Path | Purpose |
|---|---|
| `docker/backend.Dockerfile` | Backend image (Python 3.12, non-root, configuration through environment variables). Build context is the repository root. |
| `docker/frontend.Dockerfile` | `dev` target (Vite dev server, used by `compose.yaml`) and `production` target (static build served by nginx on port 8080). |
| `docker/nginx.conf` | nginx config for the production frontend image (SPA fallback, cache and security headers). |
| `map-data/` | Git-ignored folder for the offline map tile file `region.pmtiles` (README only in Git); mounted read-only into the frontend containers. See `docs/maps/OFFLINE_MAPS.md`. |
| `scripts/` | Reserved for deployment helper scripts; none yet. |

See `docs/architecture/deployment-architecture.md` for the target topology and `docs/operations/runbook.md` for the startup sequence. The local `compose.yaml` at the repository root is for development only. **No production environment is configured or claimed by this repository.**
