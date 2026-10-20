# Functional requirements

Status values: **Foundation** = schema/boundary exists, **Not started**. Nothing below is implemented as a user feature yet unless stated. Priority: M = must, S = should, C = could. IDs are stable; reference them in issues, tests and PRs.

| ID | Requirement | Module / feature | Pri | Status |
|---|---|---|---|---|
| FR-AUTH-1 | Users register/are created and sign in with email and password; passwords stored only as Argon2id hashes. | auth, users | M | Primitives only (`core/security.py`) |
| FR-AUTH-2 | Sessions use short-lived access tokens and rotating refresh tokens that can be revoked; logout revokes. | auth | M | Schema (`auth_sessions`) |
| FR-AUTH-3 | Every protected endpoint enforces server-side authorization by permission. | core/permissions | M | Primitive only |
| FR-USER-1 | Administrators manage users, roles and permissions. | users, administration | M | Schema |
| FR-REP-1 | Users create waste reports with location, description, estimated weight (kg) and images. | waste_reports | M | Schema |
| FR-REP-2 | Reports can be listed with pagination and filtered by status, reporter, date range and area. | waste_reports | M | Not started |
| FR-REP-3 | Image upload validates type, size and pixel count and stores metadata and hash. | waste_reports, ml/common | M | Preprocessing validation only |
| FR-CLS-1 | An uploaded image can be classified into identified object + waste-material category with confidences from the deployed model only. | classification | M | Schema; **no model** |
| FR-CLS-2 | Low-confidence predictions are flagged for review; reviewers confirm, correct or reject. | classification | M | Schema |
| FR-CLS-3 | Disposal guidance is shown from the sorting guide by material category. | sorting_guide | M | Schema |
| FR-COL-1 | Collection tasks are created from reports or manually, with priority and due date. | collection | M | Schema |
| FR-COL-2 | Tasks are assigned to a collector (and vehicle); only one active assignment per task. | collection | M | Schema + DB constraint |
| FR-COL-3 | Status transitions are validated and recorded in an append-only history. | collection | M | Schema |
| FR-COL-4 | Field events record arrival, collection (weight kg), skip, contamination, delivery. | collection | M | Schema |
| FR-RTE-1 | Route plans order stops for a vehicle/driver; stops are tasks or facilities. | route_planning | S | Schema |
| FR-RTE-2 | A route optimization endpoint proposes a stop order and records the optimizer used. | route_planning, integrations/mapping | S | Not started |
| FR-FAC-1 | Facilities (processing centers, depots, transfer stations, drop-off points) are managed. | facilities | M | Schema |
| FR-FLT-1 | Vehicles, capacity (kg) and availability are managed. | fleet | M | Schema |
| FR-CIR-1 | Facilities record material recovery (input/recovered kg, method). | circular_economy | M | Schema |
| FR-CIR-2 | Recovery is verified by an authorized user; only verified records count in metrics. | circular_economy | M | Schema + DB constraint |
| FR-ANA-1 | Dashboards show volumes, status counts and trends computed from real records. | analytics, dashboard | M | Not started |
| FR-FOR-1 | Waste-generation forecasts for a stated horizon, with baseline comparison and error metrics. | forecasting, ml | S | Schema; no model |
| FR-ANO-1 | Operational anomalies raise alerts with severity, expected vs observed values and an explanation. | anomaly_detection, ml | S | Schema; no detector |
| FR-INC-1 | Community members report incidents with location/photo; staff triage to resolution. | community_incidents | S | Schema |
| FR-PAS-1 | Material passports with append-only chain-of-custody events. | material_passports | C | Schema |
| FR-RWD-1 | An append-only ledger awards points idempotently per source and records verified impact (kg). | rewards | C | Schema + DB constraint |
| FR-NOT-1 | Users receive in-app notifications and can mark them read. | notifications | S | Schema |
| FR-AUD-1 | Security-relevant and administrative actions are recorded in an append-only audit log. | audit | M | Schema |
| FR-OPS-1 | `/health` reports liveness; `/ready` reports database reachability and migration state. | health | M | **Implemented** |
| FR-OPS-2 | Operators can view API liveness/readiness in the UI. | frontend settings | C | **Implemented** (System status page) |

## Acceptance
A requirement is done only when: endpoint(s)/screens exist behind authorization, tests at the layers listed in `docs/testing/testing-strategy.md` pass in CI, the API/data docs are updated, and the status above is changed in the same pull request.
