# Feature: community-incidents

Report and follow community incidents.

**Status:** not implemented (directory reserves the feature boundary only).

- **Backend module:** `community_incidents`
- **Layout when implemented:** `api/`, `components/`, `hooks/`, `pages/`, `schemas/`, `types/`, `utils/` (only those needed) and an `index.ts` that is the feature's only public interface. Other code imports `@/features/community-incidents`, never its internals (enforced by ESLint).
- Server data comes from the shared API client (`@/services/api-client`) through TanStack Query; no local mock data as a production source.
