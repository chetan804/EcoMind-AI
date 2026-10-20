# Feature: dashboard

Landing page after sign-in at `/dashboard`.

- **People with `analytics:read`** (manager, administrator) see the operations overview: KPI tiles, weekly collected-weight chart, collection tasks by status, fleet, waste reports and passports. Every figure comes from `GET /api/v1/analytics/overview` and `/weekly-trend` through the `analytics` feature's hooks; nothing is hard-coded or simulated.
- **Everyone else** sees a short list of destinations they are permitted to use.
- **Deviations from the Operational Command Center reference:** no city map (the platform stores no map layer, and a decorative map would imply data that does not exist); no waste-composition donut or environmental-impact tile (no source data; impact appears on the analytics page only as recorded ledger weight); no "Bins" KPI. See `docs/ui/screen-inventory.md`.
- **Public interface:** `import { DashboardPage } from '@/features/dashboard'`.
