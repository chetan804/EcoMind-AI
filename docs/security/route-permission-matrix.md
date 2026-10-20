# Route permission matrix

> **Generated** by `scripts/security/generate_route_matrix.py` from the mounted application and the RBAC catalog (`backend/app/modules/users/rbac.py`). Do not edit by hand; CI fails if this file is stale. `backend/tests/security/test_route_inventory.py` fails if a route becomes public or signed-in-only without being listed there.

133 operations. Authorization is decided on the server from the database on every request; hiding a button in the UI is only a convenience. Object-level rules (for example a citizen reading only their own reports) are enforced inside the services and covered by the module tests.

| Method | Path | Access | Roles that hold it |
|---|---|---|---|
| GET | `/api/v1/admin/audit-logs` | `audit:read` | administrator |
| GET | `/api/v1/admin/roles` | `users:read` | manager, administrator |
| GET | `/api/v1/admin/system` | `settings:manage` | administrator |
| GET | `/api/v1/admin/users` | `users:read` | manager, administrator |
| GET | `/api/v1/admin/users/{user_id}` | `users:read` | manager, administrator |
| POST | `/api/v1/admin/users/{user_id}/activate` | `users:manage` | administrator |
| POST | `/api/v1/admin/users/{user_id}/deactivate` | `users:manage` | administrator |
| POST | `/api/v1/admin/users/{user_id}/reset-mfa` | `users:manage` | administrator |
| PUT | `/api/v1/admin/users/{user_id}/roles` | `users:manage` | administrator |
| GET | `/api/v1/analytics/overview` | `analytics:read` | manager, administrator |
| GET | `/api/v1/analytics/weekly-trend` | `analytics:read` | manager, administrator |
| GET | `/api/v1/anomalies` | `anomalies:read` | manager, administrator |
| POST | `/api/v1/anomalies/scan` | `anomalies:manage` | manager, administrator |
| GET | `/api/v1/anomalies/{alert_id}` | `anomalies:read` | manager, administrator |
| POST | `/api/v1/anomalies/{alert_id}/acknowledge` | `anomalies:manage` | manager, administrator |
| POST | `/api/v1/anomalies/{alert_id}/false-positive` | `anomalies:manage` | manager, administrator |
| POST | `/api/v1/anomalies/{alert_id}/resolve` | `anomalies:manage` | manager, administrator |
| POST | `/api/v1/auth/change-password` | signed in | any signed-in user |
| POST | `/api/v1/auth/login` | public | anyone |
| POST | `/api/v1/auth/logout` | public (cookie + CSRF header) | anyone |
| GET | `/api/v1/auth/me` | signed in | any signed-in user |
| GET | `/api/v1/auth/mfa` | signed in | any signed-in user |
| POST | `/api/v1/auth/mfa/activate` | signed in | any signed-in user |
| POST | `/api/v1/auth/mfa/disable` | signed in | any signed-in user |
| POST | `/api/v1/auth/mfa/enroll` | signed in | any signed-in user |
| POST | `/api/v1/auth/mfa/recovery-codes` | signed in | any signed-in user |
| POST | `/api/v1/auth/mfa/verify` | public | anyone |
| POST | `/api/v1/auth/refresh` | public (cookie + CSRF header) | anyone |
| POST | `/api/v1/auth/register` | public | anyone |
| GET | `/api/v1/circular-economy/recovery-records` | `circular_economy:read` | facility_operator, manager, administrator |
| POST | `/api/v1/circular-economy/recovery-records` | `circular_economy:manage` | facility_operator, manager, administrator |
| GET | `/api/v1/circular-economy/recovery-records/summary` | `circular_economy:read` | facility_operator, manager, administrator |
| GET | `/api/v1/circular-economy/recovery-records/{record_id}` | `circular_economy:read` | facility_operator, manager, administrator |
| POST | `/api/v1/circular-economy/recovery-records/{record_id}/verify` | `circular_economy:verify` | manager, administrator |
| GET | `/api/v1/classification/model` | signed in | any signed-in user |
| GET | `/api/v1/classification/models` | `classification:manage_models` | administrator |
| POST | `/api/v1/classification/models/{version_id}/activate` | `classification:manage_models` | administrator |
| GET | `/api/v1/classification/predictions` | `classification:review` | facility_operator, manager, administrator |
| POST | `/api/v1/classification/predictions` | `classification:predict` | citizen, collector, facility_operator, manager, administrator |
| GET | `/api/v1/classification/predictions/{prediction_id}` | `classification:predict` | citizen, collector, facility_operator, manager, administrator |
| GET | `/api/v1/classification/predictions/{prediction_id}/image` | `classification:review` | facility_operator, manager, administrator |
| POST | `/api/v1/classification/predictions/{prediction_id}/review` | `classification:review` | facility_operator, manager, administrator |
| GET | `/api/v1/collection/tasks` | `collection:read` | collector, facility_operator, manager, administrator |
| POST | `/api/v1/collection/tasks` | `collection:manage` | manager, administrator |
| GET | `/api/v1/collection/tasks/{task_id}` | `collection:read` | collector, facility_operator, manager, administrator |
| POST | `/api/v1/collection/tasks/{task_id}/assign` | `collection:manage` | manager, administrator |
| POST | `/api/v1/collection/tasks/{task_id}/cancel` | `collection:manage` | manager, administrator |
| POST | `/api/v1/collection/tasks/{task_id}/complete` | `collection:execute` or `collection:manage` | collector, manager, administrator |
| POST | `/api/v1/collection/tasks/{task_id}/events` | `collection:execute` or `collection:manage` | collector, manager, administrator |
| POST | `/api/v1/collection/tasks/{task_id}/fail` | `collection:execute` or `collection:manage` | collector, manager, administrator |
| POST | `/api/v1/collection/tasks/{task_id}/reschedule` | `collection:manage` | manager, administrator |
| POST | `/api/v1/collection/tasks/{task_id}/start` | `collection:execute` or `collection:manage` | collector, manager, administrator |
| GET | `/api/v1/community-incidents` | `incidents:read_own` or `incidents:triage` | citizen, manager, administrator |
| POST | `/api/v1/community-incidents` | `incidents:create` | citizen, collector, administrator |
| GET | `/api/v1/community-incidents/summary` | `incidents:triage` | manager, administrator |
| GET | `/api/v1/community-incidents/{incident_id}` | `incidents:read_own` or `incidents:triage` | citizen, manager, administrator |
| POST | `/api/v1/community-incidents/{incident_id}/assign` | `incidents:triage` | manager, administrator |
| POST | `/api/v1/community-incidents/{incident_id}/status` | `incidents:triage` | manager, administrator |
| GET | `/api/v1/facilities` | `facilities:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/facilities` | `facilities:manage` | manager, administrator |
| GET | `/api/v1/facilities/{facility_id}` | `facilities:read` | citizen, collector, facility_operator, manager, administrator |
| PATCH | `/api/v1/facilities/{facility_id}` | `facilities:manage` | manager, administrator |
| GET | `/api/v1/fleet/vehicles` | `fleet:read` | collector, manager, administrator |
| POST | `/api/v1/fleet/vehicles` | `fleet:manage` | manager, administrator |
| GET | `/api/v1/fleet/vehicles/{vehicle_id}` | `fleet:read` | collector, manager, administrator |
| PATCH | `/api/v1/fleet/vehicles/{vehicle_id}` | `fleet:manage` | manager, administrator |
| POST | `/api/v1/forecasting/forecasts` | `forecasting:run` | manager, administrator |
| GET | `/api/v1/forecasting/forecasts/latest` | `forecasting:read` | manager, administrator |
| GET | `/api/v1/forecasting/series` | `forecasting:read` | manager, administrator |
| GET | `/api/v1/forecasting/series/history` | `forecasting:read` | manager, administrator |
| GET | `/api/v1/marketplace/listings` | `marketplace:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/marketplace/listings` | `marketplace:create` | facility_operator, manager, administrator |
| GET | `/api/v1/marketplace/listings/{listing_id}` | `marketplace:read` | citizen, collector, facility_operator, manager, administrator |
| PATCH | `/api/v1/marketplace/listings/{listing_id}` | `marketplace:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/marketplace/listings/{listing_id}/close` | `marketplace:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/marketplace/listings/{listing_id}/publish` | `marketplace:read` | citizen, collector, facility_operator, manager, administrator |
| GET | `/api/v1/marketplace/listings/{listing_id}/requests` | `marketplace:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/marketplace/listings/{listing_id}/requests` | `marketplace:request` | citizen, collector, facility_operator, manager, administrator |
| GET | `/api/v1/marketplace/requests/mine` | `marketplace:request` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/marketplace/requests/{request_id}/accept` | `marketplace:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/marketplace/requests/{request_id}/decline` | `marketplace:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/marketplace/requests/{request_id}/withdraw` | `marketplace:request` | citizen, collector, facility_operator, manager, administrator |
| GET | `/api/v1/material-passports` | `passports:read` | facility_operator, manager, administrator |
| POST | `/api/v1/material-passports` | `passports:manage` | facility_operator, manager, administrator |
| GET | `/api/v1/material-passports/by-code/{code}` | `passports:read` | facility_operator, manager, administrator |
| GET | `/api/v1/material-passports/{passport_id}` | `passports:read` | facility_operator, manager, administrator |
| POST | `/api/v1/material-passports/{passport_id}/events` | `passports:manage` | facility_operator, manager, administrator |
| GET | `/api/v1/material-passports/{passport_id}/integrity` | `passports:read` | facility_operator, manager, administrator |
| POST | `/api/v1/material-passports/{passport_id}/recovery` | `passports:manage` | facility_operator, manager, administrator |
| GET | `/api/v1/notifications` | `notifications:read_own` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/notifications/read-all` | `notifications:read_own` | citizen, collector, facility_operator, manager, administrator |
| GET | `/api/v1/notifications/unread-count` | `notifications:read_own` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/notifications/{notification_id}/read` | `notifications:read_own` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/rewards/adjustments` | `rewards:manage` | manager, administrator |
| POST | `/api/v1/rewards/entries/{entry_id}/reverse` | `rewards:manage` | manager, administrator |
| GET | `/api/v1/rewards/ledger` | `rewards:manage` | manager, administrator |
| GET | `/api/v1/rewards/ledger/summary` | `rewards:manage` | manager, administrator |
| GET | `/api/v1/rewards/me/balance` | `rewards:read_own` | citizen, administrator |
| GET | `/api/v1/rewards/me/entries` | `rewards:read_own` | citizen, administrator |
| GET | `/api/v1/route-planning/plans` | `routes:read` | collector, manager, administrator |
| POST | `/api/v1/route-planning/plans` | `routes:manage` | manager, administrator |
| GET | `/api/v1/route-planning/plans/{plan_id}` | `routes:read` | collector, manager, administrator |
| POST | `/api/v1/route-planning/plans/{plan_id}/cancel` | `routes:manage` | manager, administrator |
| POST | `/api/v1/route-planning/plans/{plan_id}/publish` | `routes:manage` | manager, administrator |
| GET | `/api/v1/route-planning/plans/{plan_id}/road-route` | `routes:read` | collector, manager, administrator |
| GET | `/api/v1/sorting-guide/categories` | `sorting_guide:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/sorting-guide/categories` | `sorting_guide:manage` | manager, administrator |
| PATCH | `/api/v1/sorting-guide/categories/{category_id}` | `sorting_guide:manage` | manager, administrator |
| GET | `/api/v1/sorting-guide/guidance` | `sorting_guide:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/sorting-guide/guidance` | `sorting_guide:manage` | manager, administrator |
| GET | `/api/v1/sorting-guide/guidance/{guidance_id}` | `sorting_guide:read` | citizen, collector, facility_operator, manager, administrator |
| PATCH | `/api/v1/sorting-guide/guidance/{guidance_id}` | `sorting_guide:manage` | manager, administrator |
| GET | `/api/v1/tracking/collections/{task_id}` | `collection:read` | collector, facility_operator, manager, administrator |
| GET | `/api/v1/tracking/config` | `fleet:read` | collector, manager, administrator |
| GET | `/api/v1/tracking/route-plans/{plan_id}` | `routes:read` | collector, manager, administrator |
| DELETE | `/api/v1/tracking/simulation/vehicles/{vehicle_id}/locations` | `fleet:simulate` | manager, administrator |
| POST | `/api/v1/tracking/simulation/vehicles/{vehicle_id}/locations` | `fleet:simulate` | manager, administrator |
| GET | `/api/v1/tracking/vehicles` | `fleet:read` | collector, manager, administrator |
| GET | `/api/v1/tracking/vehicles/{vehicle_id}` | `fleet:read` | collector, manager, administrator |
| GET | `/api/v1/tracking/vehicles/{vehicle_id}/locations` | `fleet:read` | collector, manager, administrator |
| POST | `/api/v1/tracking/vehicles/{vehicle_id}/locations` | `fleet:track` or `fleet:manage` | collector, manager, administrator |
| GET | `/api/v1/waste-reports` | `waste_reports:read_own` or `waste_reports:read_all` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/waste-reports` | `waste_reports:create` | citizen, administrator |
| POST | `/api/v1/waste-reports/media` | `waste_reports:create` | citizen, administrator |
| GET | `/api/v1/waste-reports/media/{media_id}/content` | `waste_reports:read_own` or `waste_reports:read_all` | citizen, collector, facility_operator, manager, administrator |
| GET | `/api/v1/waste-reports/{report_id}` | `waste_reports:read_own` or `waste_reports:read_all` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/waste-reports/{report_id}/review` | `waste_reports:review` | manager, administrator |
| GET | `/api/v1/zones` | `facilities:read` | citizen, collector, facility_operator, manager, administrator |
| POST | `/api/v1/zones` | `facilities:manage` | manager, administrator |
| GET | `/api/v1/zones/{zone_id}` | `facilities:read` | citizen, collector, facility_operator, manager, administrator |
| PATCH | `/api/v1/zones/{zone_id}` | `facilities:manage` | manager, administrator |
| GET | `/health` | public | anyone |
| GET | `/ready` | public | anyone |
