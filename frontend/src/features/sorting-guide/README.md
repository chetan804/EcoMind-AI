# Feature: sorting-guide

Browse material sorting guidance.

**Status:** not implemented (directory reserves the feature boundary only).

- **Backend module:** `sorting_guide`
- **Layout when implemented:** `api/`, `components/`, `hooks/`, `pages/`, `schemas/`, `types/`, `utils/` (only those needed) and an `index.ts` that is the feature's only public interface. Other code imports `@/features/sorting-guide`, never its internals (enforced by ESLint).
- Server data comes from the shared API client (`@/services/api-client`) through TanStack Query; no local mock data as a production source.
