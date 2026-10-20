# Screen inventory

Reference list of screens the product needs, mapped to features, routes and API areas. Every screen below marked **Working** renders only data returned by the backend (no mock arrays, no demonstration numbers) and shows an explicit empty, error or "not available" state otherwise. Navigation entries are filtered by the signed-in user's permissions (a UX nicety; the server enforces access). **Marketplace** has no backend and is not built; its entry stays tagged "Soon". **Locations and zones** is built over named zones without map geometry (see the table). Smart Bins & Telemetry is intentionally absent from navigation.

Test coverage: `frontend/tests/integration/{security,operations,circular,...}.test.tsx` plus component and unit tests (see `docs/project-completion/IMPLEMENTATION_STATUS.md` for counts). Real-browser renders, side-by-sides and difference images for screens 05 to 22 are in `docs/ui/evidence/screens/` (demonstration data; low similarity scores, no fidelity claim); do not read "Working" as visual fidelity.

| Screen | Route | Feature | Backend | Permission | Status |
|---|---|---|---|---|---|
| System status | `/settings/system-status` | settings | `/health`, `/ready` | signed in | **Working** |
| Not found / error / forbidden | `*` | components/feedback | none | all | **Working** |
| Landing | `/` | landing | none | public | **UI only** (static content; stats are repository facts) |
| Sign in / Sign up (with MFA step) | `/sign-in`, `/sign-up` | auth | auth, MFA | public | **Working** (registration, lockout and policy messages; second step when MFA is on) |
| Dashboard (Operational Command Center) | `/dashboard` | dashboard | analytics, notifications | `analytics:read` for figures | **Working** (real queries; clear state without permission or data) |
| Classify an item | `/classify` | waste-classification | classification | `classification:predict` | **Working** (needs an activated model; says so otherwise) |
| Waste intake records (list, report, review, classify photo, create task) | `/reports` | waste-reports | waste_reports, classification, collection | read own/all, create, review | **Working** |
| Collections (list, create, assign, start, event, complete with weight, fail, cancel, reschedule) | `/collection` | collection | collection | `collection:read`; manage / execute | **Working** |
| Route optimization (plans, stops, publish, cancel) | `/routes` | route-planning | route_planning | `routes:read`; `routes:manage` | **Working** (straight-line ordering, no ETA) |
| Fill-level forecasting | `/forecasts` | forecasting | forecasting | `forecasting:read` | **Working** |
| Anomaly detection | `/anomalies` | anomaly-alerts | anomaly_detection | `anomalies:read`; manage | **Working** ("suspected anomaly" wording) |
| Operational alerts / notifications | `/notifications` | notifications | notifications | `notifications:read_own` | **Working** (bell badge from unread count) |
| Community incident triage (report, assign, status) | `/incidents` | community-incidents | community_incidents | create / read own / triage | **Working** |
| Material sorting guide | `/sorting-guide` | sorting-guide | sorting_guide | `sorting_guide:read`; manage | **Working** (no content shipped; shows source or "no source cited") |
| Chain-of-custody passports (events, integrity check, link recovery) | `/passports` | material-passports | material_passports | `passports:read`; manage | **Working** |
| Material recovery (records, summary, verify) | `/recovery` | circular-economy | circular_economy | `circular_economy:read`; manage, verify | **Working** |
| Rewards and impact ledger (my points; ledger, adjust, reverse) | `/rewards` | rewards | rewards | `rewards:read_own`; `rewards:manage` | **Working** (no redemption exists) |
| Processing facilities and depots | `/facilities` | facilities | facilities | `facilities:read`; manage | **Working** |
| Collection fleet vehicles | `/fleet` | fleet | fleet | `fleet:read`; manage | **Working** |
| Executive analytics and reporting | `/analytics` | analytics | analytics | `analytics:read` | **Working** |
| Security and MFA (TOTP enrolment, recovery codes, change password) | `/settings/security` | settings | auth, MFA | signed in | **Working** |
| Users and roles | `/settings/users` | users | administration | `users:read`; `users:manage` | **Working** |
| Audit log | `/settings/audit` | audit | administration | `audit:read` | **Working** |
| Circular surplus marketplace | `/circular-economy` | none | **no backend** | none | **Planned** ("Soon"; nothing invented) |
| Locations and zones | `/locations` | locations | facilities (`/api/v1/zones`, `GET /facilities?zone_id=`) | `facilities:read`; manage with `facilities:manage` | **Working** (zones table, facilities per zone, create/edit/retire; **no map or boundaries**: the platform holds no verified map data, and the page says so) |
| Prediction review queue | `/classify/review` | waste-classification | classification (+ `GET /predictions/{id}/image`) | `classification:review` | **Working** (photo, suggestion, confirm / correct / reject) |
| Smart bins and sensor telemetry | none | none | none | none | **Excluded by product decision** |

## Design references

`docs/ui/reference/` holds the 22 design reference images (immutable; integrity is checked against `manifest.json` by `scripts/quality/check_structure.py`). The mapping below uses the **file titles only**; screens 05 to 22 have not been reviewed in detail and each mapping must be confirmed when its screen is built.

| Reference | Screen | Inventory row / module | Status |
|---|---|---|---|
| 01 Landing Page | Landing | landing | **UI only** |
| 02 Login / Sign Up | Sign in / Sign up | auth | **Working** |
| 03 Operational Command Center | Dashboard | dashboard | **Working** |
| 04 AI Waste Classification | Classify an item | waste-classification | **Working** (needs an active model) |
| 05 Fill Level Forecasting | Forecasts | forecasting | **Working** |
| 06 Anomaly Detection | Anomalies | anomaly-alerts | **Working** |
| 07 Route Optimization | Route plans | route-planning | **Working** |
| 08 Circular Surplus Marketplace | none | none (no backend) | **Planned** |
| 09 Community Incident Triage | Incidents | community-incidents | **Working** |
| 10 Material Sorting Guide | Sorting guide | sorting-guide | **Working** |
| 11 Chain of Custody Passports | Passports | material-passports | **Working** |
| 12 Rewards and Impact Ledger | Rewards | rewards | **Working** |
| 13 Waste Intake Records | Waste reports | waste-reports | **Working** |
| 14 Locations and Zones | `locations` | zones in the facilities module | **Built without map geometry** (evidence: `docs/ui/evidence/screens/locations-*.png`) |
| 15 Processing Facilities and Depots | Facilities | facilities | **Working** |
| 16 Collection Fleet Vehicles | Fleet | fleet | **Working** |
| 17 Smart Bins and Sensor Telemetry | none | excluded by product decision | **Not planned** |
| 18 Collections and Impact | Collections (impact from analytics and recovery) | collection | **Working** |
| 19 Waste Intake / Fleet Vehicles | unclear title | waste-reports and fleet cover both | **Working** (title ambiguity unresolved) |
| 20 Executive Analytics and Reporting | Analytics | analytics | **Working** |
| 21 Operational System Alerts | Notifications | notifications, anomaly-alerts | **Working** |
| 22 Security and MFA | Security | settings (MFA: docs/security/mfa.md) | **Working** |

Visual evidence (`docs/ui/evidence/`) exists for the first four screens only. Screenshot-versus-reference comparison for the rest is outstanding.
