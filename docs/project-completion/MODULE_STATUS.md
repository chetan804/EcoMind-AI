# Status of the 25 modules (2026-11-04)

The product brief lists 25 modules. This table states, for each, what exists and what evidence backs it. **None of the
25 screens was individually redesigned in this round.** They share one design system (tokens, `components/ui`,
shared tables, filters, empty/loading/error states) and were audited and kept; the work in this round changed the
dashboard home, role scoping, the landing and authentication screens, data, tests and documentation. Nothing here claims
a page-by-page premium redesign.

Evidence columns: **API tests** = `backend/tests/api/*`; **UI tests** = Vitest integration tests in `frontend/tests/integration`
(component-level, API mocked); **E2E** = Playwright against the real stack; **axe** = `accessibility.spec.ts` (signed-in,
administrator, dark and light). Every route is also in the permission matrix `docs/security/route-permission-matrix.md`.

| # | Module | Route | Backend | API tests | UI tests | E2E | axe | Known gap |
|---|---|---|---|---|---|---|---|---|
| 1 | Command Center | `/dashboard` | `analytics` | `test_analytics` | `role-homes`, `analytics-dashboard` | `role-homes` | yes + role homes | map card needs the tile file for a base map |
| 2 | Executive Analytics | `/analytics` | `analytics` | `test_analytics` | `analytics-dashboard` | `core-workflow` | yes | figures are only as good as the data; reconciled for the dev dataset (73/73) |
| 3 | Classification | `/classify` | `classification` | `test_classification` | `ui-pages` (classification) | `classification.spec` | yes | **no approved model**: the screen says so and offers no prediction |
| 4 | Review Queue | `/classify/review` | `classification` | `test_classification` | `review-queue` | `classification.spec` | yes | empty until a model is active |
| 5 | Collections | `/collection` | `collection` | `test_collection` (incl. collector scoping) | `operations` | `core-workflow` | yes | |
| 6 | Routes | `/routes` | `route_planning` | `test_route_planning`, `test_road_route` (incl. collector scoping) | `operations` | `tracking.spec` | yes | straight-line optimiser; road geometry only if OSRM/Google is configured |
| 7 | Forecasting | `/forecasts` | `forecasting` | `test_forecasting` | `forecasting` | none | yes | needs >= 26 weeks of history |
| 8 | Anomalies | `/anomalies` | `anomaly_detection` | `test_anomalies` | `anomalies` | none | yes | detector flagged 1 of 3 planted weeks on the dev dataset |
| 9 | Incident Triage | `/incidents` | `community_incidents` | `test_community_incidents` | `operations` | none | yes | |
| 10 | Alerts | `/notifications` | `notifications` | `test_notifications` | `notifications` | none | yes | in-app only; e-mail covers account messages only |
| 11 | Fleet | `/fleet` | `fleet`, `tracking` | `test_fleet`, `test_tracking` | `operations`, `tracking` | `tracking.spec` | yes | no real GPS device connected; labelled simulator only |
| 12 | Facilities | `/facilities` | `facilities` | `test_facilities` | `operations`, `circular` | none | yes | |
| 13 | Locations / Zones | `/locations` | `facilities` (zones) | `test_zones` | `locations` | none | yes | generated zones are approximate localities, not official wards |
| 14 | Marketplace | `/marketplace` | `marketplace` | `test_marketplace`, `test_marketplace_expiry_photos` | `marketplace` | `marketplace.spec` | yes | |
| 15 | Waste Reports | `/reports` | `waste_reports` | `test_waste_reports`, `test_waste_report_media` | `operations` | `core-workflow` | yes | collectors and operators can list every report (X6, privacy review open) |
| 16 | Sorting Guide | `/sorting-guide` | `sorting_guide` | `test_sorting_guide` | none dedicated | none | yes | no dedicated UI test; guidance rows come from the seeded reference content |
| 17 | Recovery | `/recovery` | `circular_economy` | `test_recovery_records` | `circular` | `core-workflow` | yes | |
| 18 | Passports | `/passports` | `material_passports` | `test_material_passports` | `circular` | none | yes | |
| 19 | Rewards | `/rewards` | `rewards` | `test_rewards`, `test_rewards_catalogue` | `rewards-catalogue` | `rewards-redemption.spec` | yes | |
| 20 | Help Assistant | `/assistant` | `support` | `test_support_assistant_quality` | `support` | `support.spec` | yes | retrieval over seeded articles, no generative model |
| 21 | Support | `/support` | `support` | `test_support` | `support` | `support.spec` | yes | |
| 22 | Security / MFA | `/settings/security` | `auth` | `test_mfa`, `test_mfa_enforcement` | `security` | `mfa.spec` (some steps skip without Mailpit or enforced MFA) | partly (not under `ROUTES`) | |
| 23 | User Management | `/settings/users`, `/settings/access` | `administration`, `access_requests` | `test_administration`, `test_access_requests` | `security`, `ui-pages` (sign-up role request) | `role-homes` (direct API refusals) | `/settings/users` not in the axe route list | |
| 24 | Audit Logs | `/settings/audit` | `audit` | `test_administration` | `security` | `role-homes` (403/200 per role) | not in the axe route list | generated data adds no audit rows by design |
| 25 | System Status | `/settings/system-status` | `health` | `test_health` | `SystemStatusPage` | `system-status.spec` | yes | |

Reading the gaps: a missing "UI tests" or "E2E" cell means no automated test of that kind exists today, not that the module is broken.
Pages 22-24 were not in the axe route list of `accessibility.spec.ts`; they are a candidate for the next scan.
