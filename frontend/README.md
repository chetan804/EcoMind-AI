# Frontend

React + TypeScript + Vite single-page app. Boundaries and rules: `docs/architecture/component-boundaries.md`, UI rules: `docs/ui/design-system.md`.

**State:** complete for the stated scope (status 2026-10-22). Design system, application shell, routing, one shared API client and query client, and 26 feature folders. Every data screen reads from the backend (the dashboard shows only a list of permitted destinations to roles without `analytics:read`) and is shown only to roles that hold the permission (the server enforces the same rule): dashboard, analytics, classification and its review queue, reports, collections, routes, forecasting, anomalies, incidents, alerts, vehicles, facilities, zones, marketplace, sorting guide, passports, recovery, rewards, help assistant, support desk, live tracking and maps (offline MapLibre/PMTiles by default, Google optional), users, audit, security (two-step verification) and system status. Public pages: landing, sign-in, sign-up, password reset and e-mail verification. The two smart-bin/telemetry references are excluded by product decision and are not in the navigation. The navigation model still supports a `planned` entry that opens a "not built yet" page, but none is in use. Tests: 386 Vitest tests; browser tests are in `tests/e2e`. Design rules and deviations: `docs/ui/design-system.md`.

## Layout (`src/`)
| Path | Responsibility |
|---|---|
| `app/` | `App`, `router` (single route table; each screen is code-split with React Router `lazy`), `providers`, `query-client`, `config` (only reader of `import.meta.env`), `guards/` |
| `components/` | shared UI: `ui/` design-system primitives, `layout/`, `data-display/`, `forms/`, `feedback/`, `navigation/` |
| `features/<name>/` | feature code (`api/`, `components/`, `hooks/`, `pages/`, `schemas/`, `types/`, `utils/`) exposed only via `index.ts` |
| `services/` | `api-client.ts` (the one HTTP entry point, structured `ApiError`), `error-handler.ts` |
| `hooks/`, `lib/`, `utils/`, `types/` | shared, feature-agnostic code |
| `styles/` | global CSS and design tokens |

Tests live in `tests/unit`, `tests/components`, `tests/integration` (Vitest + React Testing Library).

## Commands
```bash
npm ci               # install from lockfile
npm run dev          # http://localhost:5173
npm run lint
npm run typecheck
npm test
npm run build
```
or `make frontend-dev`, `make lint`, `make test-frontend`, `make build-frontend` from the repository root.

## Configuration
See `.env.example`. `VITE_API_BASE_URL` is the backend origin (empty = same origin, proxied in dev/preview to `DEV_PROXY_TARGET`). `VITE_*` values are public: never put secrets there. Requires Node.js 22.22+ (React Router 8).

## Rules in brief
Server state through TanStack Query and the shared API client; forms with React Hook Form + Zod; no hardcoded URLs; no mock data as a production source; features imported only through their `index.ts` (ESLint enforces it).
