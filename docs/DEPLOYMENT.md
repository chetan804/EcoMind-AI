# Deployment guide

This project includes a basic production-oriented Docker setup for the database, backend API, and frontend UI.

## Prerequisites

- Docker Desktop or Docker Engine
- Docker Compose v2

## Configure secrets

Create a root `.env` file that is excluded from Git:

```dotenv
POSTGRES_PASSWORD=use-a-unique-database-password
SECRET_KEY=generate-a-unique-random-value-at-least-32-characters-long
CORS_ORIGINS=http://localhost
```

Compose fails fast when `POSTGRES_PASSWORD` or `SECRET_KEY` is missing. The
backend also rejects known placeholder or short JWT secrets in production mode.

## Start the full stack

```bash
docker compose up --build
```

The stack exposes:

- Frontend: http://localhost
- Backend API: http://localhost:8000
- Database: localhost:5432

## Important production settings

Before deploying beyond local evaluation, configure the following values through
`.env` or the deployment secret manager:

- `SECRET_KEY`
- `CORS_ORIGINS` to your real frontend origin
- `POSTGRES_PASSWORD`
- reverse-proxy TLS settings for public access

## Operational notes

- The backend runs database migrations automatically on startup.
- The frontend is served by a static Nginx container.
- Postgres data is persisted in the `postgres_data` Docker volume.
- The default AI mode is the documented fallback classifier. External inference providers remain optional and should be configured intentionally.
