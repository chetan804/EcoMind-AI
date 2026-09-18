# EcoMind AI Architecture

EcoMind AI is currently a modular monolith: a React/Vite client calls a FastAPI API, which owns business rules and persists data in PostgreSQL through SQLAlchemy. Alembic is the only supported schema-change mechanism.

## Runtime components

- Frontend: React, TypeScript, Vite, static Nginx image.
- API: FastAPI routers, service layer, SQLAlchemy session boundary.
- Database: PostgreSQL system of record.
- AI: deterministic baseline classifiers with explicit model metadata and fallback labeling.
- Routing: local nearest-neighbor fallback; optional OSRM road legs through `ROUTING_PROVIDER=osrm`.
- Deployment: Docker Compose for PostgreSQL, API, and frontend.

## Trust boundaries

The backend is authoritative for authentication, authorization, ownership, lifecycle transitions, rewards, and operational data. The frontend never accesses the database directly. User-provided descriptions, locations, and future uploads are untrusted input.

## Current limitations

Real-time WebSockets/SSE, mobile applications, MQTT, OR-Tools, external ML providers, background workers, tenant isolation, and PostGIS are not active in the current deployment. They must be introduced behind explicit adapters and configuration rather than represented as live functionality.

## Request flow

```text
Browser -> CORS/security middleware -> FastAPI router -> domain service -> SQLAlchemy session -> PostgreSQL
                                               |-> optional AI/routing adapter
```

## Operational endpoints

- `/liveness`: process-level liveness.
- `/readiness`: database-backed readiness.
- `/health`: database health and application version.
