# Feature: community-incidents

Community incident reporting and triage.

**Status:** implemented (see `docs/ui/screen-inventory.md` for the screen and its API calls).

- **Backend module:** `community_incidents`
- Public interface is `index.ts`; other code imports `@/features/community-incidents`, never its internals (enforced by ESLint).
- Server data goes through the shared API client (`@/services/api-client`) and TanStack Query; no local mock data as a production source.
