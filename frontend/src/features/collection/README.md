# Feature: collection

Collection tasks: create, assign, start, log events, complete with weight, fail, cancel, reschedule.

**Status:** implemented (see `docs/ui/screen-inventory.md` for the screen and its API calls).

- **Backend module:** `collection`
- Public interface is `index.ts`; other code imports `@/features/collection`, never its internals (enforced by ESLint).
- Server data goes through the shared API client (`@/services/api-client`) and TanStack Query; no local mock data as a production source.
