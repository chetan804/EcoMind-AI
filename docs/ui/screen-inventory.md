# Screen inventory

Reference list of screens the product needs, mapped to features and API areas. **Only the first row exists.** Screens are built in feature milestones (see `docs/project-roadmap.md`); no placeholder pages are created in advance. Roles are provisional until the authorization milestone.

| Screen | Route (proposed) | Feature | Backend | Primary roles | Status |
|---|---|---|---|---|---|
| System status | `/settings/system-status` | settings | `/health`, `/ready` | operators | **Implemented** |
| Not found / error | `*` | components/feedback | — | all | **Implemented** |
| Sign in / sign out | `/sign-in` | auth | auth | all | Not started |
| Dashboard | `/dashboard` | dashboard | analytics | managers | Not started |
| Classify an item (upload, object + material + confidence + guidance) | `/classify` | waste-classification | classification, sorting_guide | citizens, staff | Not started |
| Prediction review queue | `/classification/review` | waste-classification | classification | staff | Not started |
| Waste reports list / detail / create | `/reports`, `/reports/:id`, `/reports/new` | waste-reports | waste_reports | citizens, staff | Not started |
| Collection tasks list / detail | `/collection`, `/collection/:id` | collection | collection | managers, collectors | Not started |
| My tasks (mobile-friendly) | `/collection/mine` | collection | collection | collectors | Not started |
| Route plans / route detail | `/routes`, `/routes/:id` | route-planning | route_planning | managers, drivers | Not started |
| Facilities | `/facilities`, `/facilities/:id` | facilities | facilities | managers, operators | Not started |
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
