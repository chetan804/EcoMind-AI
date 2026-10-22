# Screen inventory

Reference list of screens the product needs, mapped to features, routes and API areas. Every screen below marked **Working** renders only data returned by the backend (no mock arrays, no demonstration numbers) and shows an explicit empty, error or "not available" state otherwise. Navigation entries are filtered by the signed-in user's permissions (a UX nicety; the server enforces access). **Marketplace** is a matching board (listings and requests; listings expire and carry up to four photos; no price, payment, delivery or chat). **Locations and zones** is built over named zones without boundary geometry (see the table). Maps (Google Maps, with a labelled list fallback when no key is configured) appear on the command center, fleet, collection task, route plan, facilities, locations, waste reports and incidents screens; see `docs/maps/GOOGLE_MAPS_INTEGRATION.md`. Smart Bins & Telemetry is intentionally absent from navigation.

Test coverage: `frontend/tests/integration/{security,operations,circular,...}.test.tsx` plus component and unit tests (see `docs/project-completion/IMPLEMENTATION_STATUS.md` for counts). Real-browser renders, side-by-sides and difference images for screens 05 to 22 are in `docs/ui/evidence/screens/` (demonstration data; low similarity scores, no fidelity claim); do not read "Working" as visual fidelity.

| Screen | Route | Feature | Backend | Permission | Status |
|---|---|---|---|---|---|
| System status | `/settings/system-status` | settings | `/health`, `/ready` | signed in | **Working** |
| Not found / error / forbidden | `*` | components/feedback | none | all | **Working** |
| Landing | `/` | landing | none | public | **UI only** (static content; stats are repository facts) |
| Sign in / Sign up (with MFA step) | `/sign-in`, `/sign-up` | auth | auth, MFA | public | **Working** (registration, lockout and policy messages; second step when MFA is on) |
| Forgot / reset password, confirm e-mail address | `/forgot-password`, `/reset-password`, `/verify-email` | auth | auth (`/auth/password-reset/*`, `/auth/email-verification/*`; docs/operations/account-recovery.md) | public | **Working** (identical answer for known and unknown addresses; a link is never confirmed until the user presses the button; real SMTP delivery unverified) |
| Dashboard (Operational Command Center) | `/dashboard` | dashboard | analytics, notifications | `analytics:read` for figures | **Working** (real queries; clear state without permission or data). Fleet map with live/delayed/stale/simulated positions and facilities (`fleet:read`) |
| Classify an item | `/classify` | waste-classification | classification | `classification:predict` | **Working** (needs an activated model; says so otherwise) |
| Waste intake records (list, report, review, classify photo, create task) | `/reports` | waste-reports | waste_reports, classification, collection | read own/all, create, review | **Working** |
| Collections (list, create, assign, start, event, complete with weight, fail, cancel, reschedule) | `/collection` | collection | collection | `collection:read`; manage / execute | **Working** |
| Route optimization (plans, stops, publish, cancel) | `/routes` | route-planning | route_planning | `routes:read`; `routes:manage` | **Working** (straight-line ordering, no ETA; map with provider road route when `GOOGLE_MAPS_SERVER_API_KEY` is set, otherwise labelled straight lines; collector location sharing and simulator controls) |
| Fill-level forecasting | `/forecasts` | forecasting | forecasting | `forecasting:read` | **Working** |
| Anomaly detection | `/anomalies` | anomaly-alerts | anomaly_detection | `anomalies:read`; manage | **Working** ("suspected anomaly" wording) |
| Operational alerts / notifications | `/notifications` | notifications | notifications | `notifications:read_own` | **Working** (bell badge from unread count) |
| Community incident triage (report, assign, status) | `/incidents` | community-incidents | community_incidents | create / read own / triage | **Working** |
| Material sorting guide | `/sorting-guide` | sorting-guide | sorting_guide | `sorting_guide:read`; manage | **Working** (no content shipped; shows source or "no source cited") |
| Chain-of-custody passports (events, integrity check, link recovery) | `/passports` | material-passports | material_passports | `passports:read`; manage | **Working** |
| Material recovery (records, summary, verify) | `/recovery` | circular-economy | circular_economy | `circular_economy:read`; manage, verify | **Working** |
| Rewards and impact ledger (my points; catalogue and redeem with a claim code; my redemptions; staff: ledger, adjust, reverse, items, redemption queue) | `/rewards` | rewards | rewards (`/api/v1/rewards/*`, docs/api/rewards-api.md) | `rewards:read_own`; `rewards:redeem`; `rewards:manage` | **Working** (hand-over redemption only: no shipping, payment or partner integration) |
| Help assistant (chat that quotes help articles and reads the person's own points, reports and requests; says when it does not know; sends the question to staff) | `/assistant` | support | support (`/api/v1/support/assistant/*`, docs/api/support-api.md) | `support:ask` | **Working** (retrieval only, no generated text; quality: docs/ml/support-assistant.md; evidence: `docs/ui/evidence/screens/assistant-render.png`) |
| Support (my requests; staff: queue, assistant usage, help-article editor) | `/support` | support | support (`/api/v1/support/tickets`, `/articles`) | `support:ask`; `support:manage`; `knowledge:manage` | **Working** (evidence: `support-queue-render.png`, `support-articles-render.png`; no e-mail to requesters, in-app notifications only) |
| Processing facilities and depots | `/facilities` | facilities | facilities | `facilities:read`; manage | **Working** |
| Collection fleet vehicles | `/fleet` | fleet | fleet | `fleet:read`; manage | **Working** (fleet map, per-vehicle position status, tracking API `/api/v1/tracking/*`) |
| Executive analytics and reporting | `/analytics` | analytics | analytics | `analytics:read` | **Working** |
| Security and MFA (TOTP enrolment, recovery codes, change password) | `/settings/security` | settings | auth, MFA | signed in | **Working** |
| Users and roles | `/settings/users` | users | administration | `users:read`; `users:manage` | **Working** |
| Audit log | `/settings/audit` | audit | administration | `audit:read` | **Working** |
| Circular surplus marketplace | `/marketplace` | `marketplace` | `/api/v1/marketplace/*` (docs/api/marketplace-api.md) | `marketplace:read` | **Working** (matching board: listing expiry and renewal, closing outcome, up to four photos; no price, payment, delivery or chat) |
| Locations and zones | `/locations` | locations | facilities (`/api/v1/zones`, `GET /facilities?zone_id=`) | `facilities:read`; manage with `facilities:manage` | **Working** (zones table, facilities per zone, create/edit/retire; map of the zone's facilities; **no zone boundaries** because the platform holds no boundary data, and the page says so) |
| Prediction review queue | `/classify/review` | waste-classification | classification (+ `GET /predictions/{id}/image`) | `classification:review` | **Working** (photo, suggestion, confirm / correct / reject) |
| Smart bins and sensor telemetry | none | none | none | none | **Excluded by product decision** |

## Design references

`docs/ui/reference/` holds the 22 design reference images (immutable; integrity is checked against `manifest.json` by `scripts/quality/check_structure.py`). The mapping below was made from the file titles and then confirmed screen by screen when each was built; the confirmed mapping with the browser evidence is `docs/project-completion/SCREEN_TRACEABILITY.md`. Where a title is ambiguous (19) the note says so. A person with design authority has not signed off the renders.

| Reference | Screen | Inventory row / module | Status |
|---|---|---|---|
| 01 Landing Page | Landing | landing | **UI only** |
| 02 Login / Sign Up | Sign in / Sign up | auth | **Working** |
| 03 Operational Command Center | Dashboard | dashboard | **Working** |
| 04 AI Waste Classification | Classify an item | waste-classification | **Working** (needs an active model) |
| 05 Fill Level Forecasting | Forecasts | forecasting | **Working** |
| 06 Anomaly Detection | Anomalies | anomaly-alerts | **Working** |
| 07 Route Optimization | Route plans | route-planning | **Working** |
| 08 Circular Surplus Marketplace | Marketplace | marketplace | **Working** |
| 09 Community Incident Triage | Incidents | community-incidents | **Working** |
| 10 Material Sorting Guide | Sorting guide | sorting-guide | **Working** |
| 11 Chain of Custody Passports | Passports | material-passports | **Working** |
| 12 Rewards and Impact Ledger | Rewards | rewards | **Working** |
| 13 Waste Intake Records | Waste reports | waste-reports | **Working** |
| 14 Locations and Zones | `locations` | zones in the facilities module | **Built with a facilities map but no zone boundaries** (evidence: `docs/ui/evidence/screens/locations-*.png`, `docs/ui/evidence/maps/locations-zones.png`) |
| 15 Processing Facilities and Depots | Facilities | facilities | **Working** |
| 16 Collection Fleet Vehicles | Fleet | fleet | **Working** |
| 17 Smart Bins and Sensor Telemetry | none | excluded by product decision | **Not planned** |
| 18 Collections and Impact | Collections (impact from analytics and recovery) | collection | **Working** |
| 19 Waste Intake / Fleet Vehicles | unclear title | waste-reports and fleet cover both | **Working** (title ambiguity unresolved) |
| 20 Executive Analytics and Reporting | Analytics | analytics | **Working** |
| 21 Operational System Alerts | Notifications | notifications, anomaly-alerts | **Working** |
| 22 Security and MFA | Security | settings (MFA: docs/security/mfa.md) | **Working** |

Real-browser renders, side-by-side images and difference images exist in `docs/ui/evidence/` (first four screens) and `docs/ui/evidence/screens/` (the authenticated screens); the structural-similarity numbers are low for every screen and **no pixel-perfect claim is made** (see `SCREEN_TRACEABILITY.md`).
