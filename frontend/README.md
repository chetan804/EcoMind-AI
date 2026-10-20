# Frontend

React + TypeScript + Vite single-page app. Boundaries and rules: `docs/architecture/component-boundaries.md`, UI rules: `docs/ui/design-system.md`.

**State:** application shell, routing, shared API client, query client, and one real screen: **System status** (`/settings/system-status`), which displays the backend's `/health` and `/ready` responses. All other feature folders are reserved boundaries (see each `README.md`).

## Layout (`src/`)
| Path | Responsibility |
|---|---|
| `app/` | `App`, `router` (single route table), `providers`, `query-client`, `config` (only reader of `import.meta.env`), `guards/` |
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
