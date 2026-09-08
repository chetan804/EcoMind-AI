# Deployment guide

This project includes a basic production-oriented Docker setup for the database, backend API, and frontend UI.

## Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose v2

## Start the full stack

```bash
docker compose up --build
```

The stack exposes:

- Frontend: http://localhost
- Backend API: http://localhost:8000
- Database: localhost:5432

## Important production settings

Before deploying beyond local evaluation, update the following values:

- `SECRET_KEY` in `docker-compose.yml`
- `CORS_ORIGINS` to your real frontend origin
- `DATABASE_URL` credentials and database name if needed
- reverse-proxy TLS settings for public access

## Operational notes

- The backend runs database migrations automatically on startup.
- The frontend is served by a static Nginx container.
- Postgres data is persisted in the `postgres_data` Docker volume.
- The default AI mode is the documented fallback classifier. External inference providers remain optional and should be configured intentionally.
