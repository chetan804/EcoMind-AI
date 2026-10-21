# Screen traceability

Maps each of the 22 reference images in `docs/ui/reference/` (immutable; checksums verified by
`scripts/quality/check_structure.py`) to the implemented screen, its tests and its visual evidence.
Generated from `docs/ui/screen-inventory.md`, `docs/ui/evidence/` and `docs/ui/evidence/screens/metrics.json`; edit those, then
this table.

**How to read it.** SSIM is a structural-similarity number between a real browser render and the reference crop. Every value
is low because the references are small blurry composites with a caption band; **no visual-fidelity or pixel-perfect claim is made**. The
side-by-side images are the evidence. The renders in `evidence/screens/` for 03, 07, 14, 15, 16 and 18 predate the Google Maps work
(2026-10-21); `evidence/maps/` has newer renders of the map-bearing screens (see its README: they show the no-key fallback, not Google tiles). Test names are
files in `frontend/tests/integration/` (and `frontend/tests/unit/`). End-to-end specs are in `tests/e2e/specs/`.

| Ref | Reference screen | Route | Feature (`frontend/src/features/`) | Evidence (`docs/ui/evidence/`) | SSIM | Frontend tests | Notes |
|---|---|---|---|---|---|---|---|
| 01 | Landing Page | / | landing | landing-* | 0.340 | app-routing, ui-pages | UI only: static content, stats are repository facts; no demo video (control disabled) |
| 02 | Login / Sign Up | /sign-in, /sign-up | auth | sign-in-* | 0.523 | security, app-routing, auth-forms | MFA second step when enabled |
| 03 | Operational Command Center | /dashboard | dashboard | dashboard-*, screens/dashboard-data-* | 0.573 / 0.578 | analytics-dashboard, tracking | Fleet map layer added 2026-10-21 (list fallback without a key); screenshots in `maps/command-center.png` |
| 04 | AI Waste Classification | /classify | waste-classification | classification-* | 0.538 | ui-pages, review-queue | Needs an activated model; none is default |
| 05 | Fill Level Forecasting | /forecasts | forecasting | screens/forecasting-* | 0.334 | forecasting |  |
| 06 | Anomaly Detection | /anomalies | anomaly-alerts | screens/anomalies-* | 0.334 | anomalies |  |
| 07 | Route Optimization | /routes | route-planning | screens/routes-* | 0.362 | operations, tracking | Map: provider road route or labelled straight lines; evidence after maps in `maps/route-optimization.png` |
| 08 | Circular Surplus Marketplace | /marketplace | marketplace | screens/marketplace-* | 0.238 | marketplace | Matching board only; no map (no location field) |
| 09 | Community Incident Triage | /incidents | community-incidents | screens/incidents-* | 0.261 | operations | Map with status-only labels, no reporter identity |
| 10 | Material Sorting Guide | /sorting-guide | sorting-guide | screens/sorting-guide-* | 0.388 | circular |  |
| 11 | Chain of Custody Passports | /passports | material-passports | screens/passports-* | 0.353 | circular | No map (no recorded movement events) |
| 12 | Rewards and Impact Ledger | /rewards | rewards | screens/rewards-* | 0.427 | circular |  |
| 13 | Waste Intake Records | /reports | waste-reports | screens/reports-* | 0.424 | operations | Location picker and clustered map |
| 14 | Locations and Zones | /locations | locations | screens/locations-*, maps/locations-zones.png | 0.297 | locations, tracking | Facilities map; no zone boundaries (no data) |
| 15 | Processing Facilities and Depots | /facilities | facilities | screens/facilities-* | 0.264 | operations | Map and keyless Directions links |
| 16 | Collection Fleet Vehicles | /fleet | fleet, tracking | screens/fleet-*, maps/fleet.png | 0.440 | operations, tracking, tracking (unit) | Live/delayed/stale/simulated labels; unavailable when never reported |
| 17 | Smart Bins and Sensor Telemetry | none | none | none | - | - | Excluded by product decision; not in navigation |
| 18 | Collections and Impact | /collection | collection | screens/collection-*, maps/collection-tracking.png | 0.336 | operations, tracking | Tracking map and collector location sharing in the task dialog |
| 19 | Waste Intake / Fleet Vehicles | /reports, /fleet | waste-reports, fleet | (see 13, 16) | - | (see 13, 16) | Title ambiguous; covered by 13 and 16 |
| 20 | Executive Analytics and Reporting | /analytics | analytics | screens/analytics-* | 0.359 | analytics-dashboard | No map: no geographic analytics API |
| 21 | Operational System Alerts | /notifications | notifications, anomaly-alerts | screens/notifications-* | 0.491 | notifications |  |
| 22 | Security and MFA | /settings/security | settings | screens/security-* | 0.397 | security |  |

## States covered per screen

Every working screen renders loading, empty, error and success states through the shared `QueryBoundary`, `Alert` and table
components, filters its navigation entry by permission, and is keyboard operable (dialogs trap focus; map markers have a text
list alternative). Responsive behaviour was checked at 1440 px (0 px horizontal overflow on the 15 captured screens) and in
`evidence/responsive-contact-sheet.jpg`. Contrast of the design tokens is checked in CI (`scripts/quality/check_contrast.py`) and axe-core runs on 20 routes in both themes; keyboard-only and screen-reader review is **not done**
(`LIMITATIONS.md`).

## Map-bearing screens (section 27)

| Screen | Map content | Without a Google key | Evidence |
|---|---|---|---|
| Dashboard / command center | vehicles + facilities, simulated layer toggle | labelled list with status and time | `maps/command-center.png` |
| Fleet | same, simulated layer on | labelled list | `maps/fleet.png` |
| Collection task dialog | planned point, vehicle, recorded path, location sharing | labelled list | `maps/collection-tracking.png` |
| Route plan dialog | numbered stops, road or straight route, progress | straight lines labelled "not roads" | `maps/route-optimization.png` |
| Locations and zones | facilities of the zone (no boundaries) | labelled list | `maps/locations-zones.png` |
| Facilities, waste reports, incidents | picker and clustered map | labelled list + manual coordinates | (no dedicated capture) |
| Marketplace, passports, executive analytics | none: no data to map | n/a | n/a |
