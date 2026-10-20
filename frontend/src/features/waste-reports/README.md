# Feature: waste-reports

Create, list, filter and view waste reports.

**Status:** implemented (see `docs/ui/screen-inventory.md` for the screen and its API calls).

- **Backend module:** `waste_reports`
- **Layout when implemented:** `api/`, `components/`, `hooks/`, `pages/`, `schemas/`, `types/`, `utils/` (only those needed) and an `index.ts` that is the feature's only public interface. Other code imports `@/features/waste-reports`, never its internals (enforced by ESLint).
- Server data comes from the shared API client (`@/services/api-client`) through TanStack Query; no local mock data as a production source.
