# Screen inventory

Reference list of screens the product needs, mapped to features and API areas. **Six screens have a UI** (Classify is now functional) (System status, Not found, Landing, Sign in / Sign up, Dashboard, Classify). System status and **Sign in / Sign up / Sign out** talk to the backend (real authentication; see `docs/api/auth-api.md`); all pages other than Landing and the auth pages now require a signed-in user. The Landing, Sign-in/Sign-up, Dashboard and Classify UIs are the Stage 1 UI milestone: they render labelled demonstration content or an honest "not available yet" state (see `design-system.md`). Everything else is **Not started**: sidebar entries for those screens route to a "planned, not built" page and are tagged "Soon". Roles are provisional until the authorization milestone.

| Screen | Route (proposed) | Feature | Backend | Primary roles | Status |
|---|---|---|---|---|---|
| System status | `/settings/system-status` | settings | `/health`, `/ready` | operators | **Implemented** |
| Not found / error | `*` | components/feedback | — | all | **Implemented** |
| Landing | `/` | landing | — | public | **UI only** (static content; stats are repository facts, not product metrics) |
| Sign in / Sign up | `/sign-in`, `/sign-up` | auth | auth | all | **Implemented** (real registration and sign-in; server errors, rate-limit and policy messages; return-to-page after sign-in) |
| Dashboard (Operational Command Center) | `/dashboard` | dashboard | analytics | managers | **UI only** (labelled demonstration data; no analytics API) |
| Classify an item (upload, object + material + confidence + guidance) | `/classify` | waste-classification | classification, sorting_guide | citizens, staff | **Working** (real upload, prediction, calibrated confidence, needs-review state; review form for reviewers). Needs an activated model artifact; without one the page says so |
| Sign out | account menu | auth | auth | all | **Implemented** (revokes the server session, clears the client session and query cache) |
| Prediction review queue | `/classification/review` | waste-classification | classification | staff | Not started |
| Waste reports list / detail / create | `/reports`, `/reports/:id`, `/reports/new` | waste-reports | waste_reports | citizens, staff | Not started (API implemented and tested; no UI yet) |
| Collection tasks list / detail | `/collection`, `/collection/:id` | collection | collection | managers, collectors | Not started |
| My tasks (mobile-friendly) | `/collection/mine` | collection | collection | collectors | Not started |
| Route plans / route detail | `/routes`, `/routes/:id` | route-planning | route_planning | managers, drivers | Not started |
| Facilities | `/facilities`, `/facilities/:id` | facilities | facilities | managers, operators | Not started (API implemented and tested; no UI yet) |
| Fleet | `/fleet` | fleet | fleet | managers | Not started |
| Recovery records and verification | `/circular-economy` | circular-economy | circular_economy | operators, verifiers | Not started |
| Analytics and trends | `/analytics` | analytics | analytics | managers | Not started |
| Forecasts | `/forecasts` | forecasting | forecasting | managers | Not started |
| Anomaly alerts | `/alerts` | anomaly-alerts | anomaly_detection | managers | Not started |
| Community incidents list / report | `/incidents`, `/incidents/new` | community-incidents | community_incidents | citizens, staff | Not started |
| Sorting guide | `/sorting-guide` | sorting-guide | sorting_guide | all | Not started |
| Material passport and custody timeline | `/passports/:id` | material-passports | material_passports | operators | Not started |
| Rewards and impact | `/rewards` | rewards | rewards | citizens | Not started |
| Notifications | `/notifications` | notifications | notifications | all | Not started |
| User and role administration | `/admin/users` | users | users | administrators | Not started |
| Audit log | `/admin/audit` | audit | audit | administrators | Not started |

**Not on the list by design:** Smart Bins & Telemetry (no hardware; see `docs/architecture/component-boundaries.md`).

## Design references

`docs/ui/reference/` holds the 22 design reference images (immutable; integrity is checked against `manifest.json` by `scripts/quality/check_structure.py`). The mapping below uses the **file titles only**; screens 05 to 22 have not been reviewed in detail and each mapping must be confirmed when its screen is built.

| Reference | Screen | Inventory row / module | Status |
|---|---|---|---|
| 01 Landing Page | Landing | landing | **UI only** |
| 02 Login / Sign Up | Sign in / Sign up | auth | **Implemented** |
| 03 Operational Command Center | Dashboard | dashboard (analytics) | **UI only** |
| 04 AI Waste Classification | Classify an item | waste-classification | **Working** (needs an active model) |
| 05 Fill Level Forecasting | Forecasts | forecasting | Not started |
| 06 Anomaly Detection | Anomaly alerts | anomaly-alerts | Not started |
| 07 Route Optimization | Route plans | route-planning | Not started |
| 08 Circular Surplus Marketplace | Recovery records and verification | circular-economy | Not started |
| 09 Community Incident Triage | Community incidents | community-incidents | Not started |
| 10 Material Sorting Guide | Sorting guide | sorting-guide | Not started |
| 11 Chain of Custody Passports | Material passport and custody timeline | material-passports | Not started |
| 12 Rewards and Impact Ledger | Rewards and impact | rewards | Not started |
| 13 Waste Intake Records | Waste reports | waste-reports (closest row; titles differ) | Not started |
| 14 Locations and Zones | Locations and zones | **no dedicated row or module yet**: owner to be decided (facilities is the closest) | Not started |
| 15 Processing Facilities and Depots | Facilities | facilities | Not started (API implemented and tested; no UI yet) |
| 16 Collection Fleet Vehicles | Fleet | fleet | Not started |
| 17 Smart Bins and Sensor Telemetry | none | **excluded by product decision** (no hardware; no nav item, no simulated telemetry) | Not planned |
| 18 Collections and Impact | Collection tasks | collection (impact figures come from analytics) | Not started |
| 19 Waste Intake / Fleet Vehicles | unclear title | waste-reports or fleet; **confirm against the image before building** | Not started |
| 20 Executive Analytics and Reporting | Analytics and trends | analytics | Not started |
| 21 Operational System Alerts | Alerts / notifications | anomaly-alerts, notifications | Not started |
| 22 Security and MFA | Account security | auth (TOTP MFA backend implemented: docs/security/mfa.md) | Backend ready; screen not started |

Visual evidence for the four built screens is in `docs/ui/evidence/`.
