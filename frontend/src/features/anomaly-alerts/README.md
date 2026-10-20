# Feature: anomaly-alerts

Suspected anomaly alerts and their review lifecycle.

**Status:** implemented (see `docs/ui/screen-inventory.md` for the screen and its API calls).

- **Backend module:** `anomaly_detection`
- Public interface is `index.ts`; other code imports `@/features/anomaly-alerts`, never its internals (enforced by ESLint).
- Server data goes through the shared API client (`@/services/api-client`) and TanStack Query; no local mock data as a production source.
