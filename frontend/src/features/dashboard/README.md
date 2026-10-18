# Feature: dashboard

Operational Command Center at `/dashboard`: KPI tiles, waste-generation trend, city map, critical alerts, waste composition and environmental impact.

**Status:** UI implemented (Stage 1 UI milestone) on **demonstration data only**. There is no analytics API yet, so nothing on this page is live or measured.

- **Backend module (future):** `analytics`.
- **Data:** `fixtures/` holds the demo values. Every data region is covered by a visible `DemoDataNotice` ("Demonstration data, not live" in the header, "Sample layout" on the map) and the charts expose their data to assistive technology. When `analytics` exists, replace the fixtures with TanStack Query hooks over `@/services/api-client`, keep the notice for any value that is still sample, and delete the fixtures that are no longer used.
- **Map:** `DemoMap` is an original inline SVG with sample pins (`components/map-config.ts` holds colours and legend). It is not a real map and is not tied to the `mapping` integration.
- **Deviations from the reference:** no "Bins" KPI or legend entry (replaced by "Open reports" and Reports / Collections / Facilities / Alerts); time-of-day greeting with no user name; the unreadable element left of the search field is omitted. See `docs/ui/design-system.md`.
- **Public interface:** `import { DashboardPage } from '@/features/dashboard'`.
