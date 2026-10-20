# Circular economy (recovery records) API

Base path `/api/v1/circular-economy`. Bearer authentication; standard error envelope; pagination `page`/`page_size`.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /recovery-records` | `circular_economy:read` | List (`facility_id`, `material_category_id`, `recovery_method`, `status`, `date_from`, `date_to`, `sort_by`, `order`) |
| `POST /recovery-records` | `circular_economy:manage` | Record processed material (`201`, always `pending`) |
| `GET /recovery-records/{id}` | `circular_economy:read` | One record |
| `POST /recovery-records/{id}/verify` | `circular_economy:verify` | `{decision: verified|rejected, notes}` |
| `GET /recovery-records/summary` | `circular_economy:read` | Recovery metrics (verified records only) |

Facility operators record; managers and administrators verify (migration 0002).

## Rules

* `facility_id` must be an active facility, `material_category_id` an active category, `collection_task_id` (optional) a **completed** task. `recovered_weight_kg ≤ input_weight_kg`, `input_weight_kg > 0`, `processed_at` timezone-aware and not in the future (`422` otherwise). Unknown fields are rejected, so a client cannot create a pre-verified record.
* **Separation of duties:** the author of a record cannot verify or reject it (`403 self_verification_forbidden`). A decided record cannot be decided again (`409 recovery_already_decided`). Rejection requires `notes`.
* Records are never edited: a wrong record is rejected and a new one entered.
* **Summary** counts `verified` records only; `pending` and `rejected` are reported separately as counts and never enter the weights. `recovery_rate = recovered / input` (a mass ratio recorded by facility staff). It is **not** a landfill-diversion, carbon or environmental-benefit claim; the response `basis` field says so. Breakdowns by material category and by recovery method.

Audit events: `recovery_record.created|verified|rejected`.
