# Component boundaries, module ownership and dependency rules

## Top-level responsibilities
| Directory | Responsibility | May depend on |
|---|---|---|
| `frontend/` | Browser UI. Talks to the backend only through `/api/v1` (+ `/health`, `/ready`). | nothing in this repo at build time |
| `backend/` | The only application server and the **only writer** of the database. | `ml/` inference code (planned) |
| `ml/` | Training, evaluation, inference. Never imports `backend/app`. | `datasets/` manifests |
| `datasets/` | Data descriptions (manifests); data files are not tracked. | — |
| `deployment/` | Container build definitions. | `frontend/`, `backend/` |
| `tests/` | Cross-application tests (e2e, contract, smoke). | running stack / `backend` app |
| `scripts/` | Developer and quality helper scripts. | — |
| `docs/` | Documentation; must agree with the code (parts are generated). | — |

There is exactly one frontend application and one backend application. Adding another application root requires an ADR; `scripts/quality/check_structure.py` fails on unexpected top-level entries.

## Backend layers
```
api/router.py → api/v1/router.py → modules/<name>/router.py   (HTTP only)
                                   modules/<name>/service.py   (business rules, transactions)
                                   modules/<name>/repository.py (queries; never commits)
                                   modules/<name>/models.py    (tables owned by the module)
core/  config, security, logging, exceptions, middleware, permissions  (infrastructure, no domain)
db/    Base, session, metadata registration (no domain)
common/ pagination, shared enums, response schemas, time (no business logic)
integrations/  adapters to external systems (file storage, mapping, email, sensors)
health/ liveness and readiness
```
Rules:
1. Routers contain no business rules; services contain no HTTP concepts.
2. A module's tables are written only by that module. Cross-module changes call the other module's **service interface** within one transaction owned by the caller; no ad hoc SQL against foreign tables.
3. Module services never import another module's router. Routers are registered only in `api/v1/router.py`.
4. Foreign keys may reference tables of modules earlier in the dependency order below (no cycles).
5. `core/`, `db/`, `common/` never import from `modules/`, with one exception: `db/metadata.py` imports every module's models for Alembic.
6. Read-only aggregation (`analytics`) goes through other modules' service/read interfaces.
7. New module files follow the contract (`router.py`, `schemas.py`, `models.py`, `repository.py`, `service.py`, `dependencies.py`, `permissions.py`, `constants.py`, `README.md`); only files that are needed are created.

## Module ownership and dependency order
Each module owns the tables listed; "Depends on" lists tables/services it references. Order is the registration order in `db/metadata.py`.

| # | Module | Owns tables | Depends on |
|---|---|---|---|
| 1 | `users` | users, roles, permissions, user_roles, role_permissions | — |
| 2 | `auth` | auth_sessions | users |
| 3 | `sorting_guide` | material_categories, sorting_guidance | — |
| 4 | `facilities` | facilities | — |
| 5 | `fleet` | fleet_vehicles | facilities |
| 6 | `waste_reports` | waste_reports, media_assets | users |
| 7 | `classification` | classification_model_versions, classification_predictions | users, sorting_guide, waste_reports |
| 8 | `collection` | collection_tasks, collection_assignments, collection_task_status_history, collection_events | users, facilities, fleet, waste_reports |
| 9 | `route_planning` | route_plans, route_stops | users, facilities, fleet, collection |
| 10 | `circular_economy` | recovery_records | users, facilities, sorting_guide, waste_reports (media), collection |
| 11 | `material_passports` | material_passports, custody_events | users, facilities, sorting_guide, collection, circular_economy |
| 12 | `community_incidents` | community_incidents | users, waste_reports (media) |
| 13 | `rewards` | reward_ledger_entries | users |
| 14 | `notifications` | notifications | users |
| 15 | `forecasting` | forecast_results | facilities, sorting_guide |
| 16 | `anomaly_detection` | anomaly_alerts | users, facilities, sorting_guide |
| 17 | `audit` | audit_logs | users |
| — | `analytics` | none (read-only) | collection, waste_reports, circular_economy, facilities |
| — | `administration` | none | users, audit |

Polymorphic references without foreign keys (documented trade-off): `reward_ledger_entries.source_id`, `notifications.entity_id`, `audit_logs.entity_id`.

## Domain ownership (specification section 6)
1 Authentication → `auth`; 2 User/role administration → `users` (+ `administration`); 3 Reports and media → `waste_reports`; 4 Recognition and material classification → `classification` (+ `sorting_guide` for categories); 5 Collection → `collection`; 6 Routes → `route_planning`; 7 Facilities → `facilities`; 8 Fleet → `fleet`; 9 Circular economy → `circular_economy`; 10 Analytics → `analytics`; 11 Forecasting → `forecasting`; 12 Anomalies → `anomaly_detection`; 13 Community incidents → `community_incidents`; 14 Sorting guidance → `sorting_guide`; 15 Passports and custody → `material_passports`; 16 Rewards and impact → `rewards`; 17 Notifications → `notifications`; 18 Audit and administration → `audit`, `administration`.

## Frontend boundaries
```
app/        composition root: App, router (single route table), providers, query client, config, guards
components/ shared UI only: ui/ (design system), layout/, data-display/, forms/, feedback/, navigation/
features/<name>/  one folder per feature; public API is index.ts only (ESLint forbids deep imports)
services/   the single API client and error handler
hooks/ lib/ utils/ types/ styles/   shared, feature-agnostic
```
`features/landing` is the one feature with no backend module (the public page at `/`); it is listed as a known feature in `scripts/quality/check_structure.py`. `features/dashboard`, `waste-classification` and `auth` currently contain UI only: see their READMEs and `docs/ui/design-system.md` for what is demonstration content and what is unavailable.

The design-reference PNGs and `manifest.json` at the repository root (committed on `main`) are tolerated by exact filename pattern in `check_structure.py`; moving them under `docs/ui/` would remove that exception.

Rules: features do not import other features' internals; shared components never import from features; there is one API client, one modal/table/button system, one authentication implementation (in `features/auth` + `app/guards`); API origin only from `app/config.ts`; no mock arrays as production data.

## Sensors
`backend/app/integrations/sensors/` is an internal, optional adapter boundary. No sensor tables, no navigation entry, and simulated readings are never presented as live data until hardware and a requirement exist.
