# Collections API

Base path `/api/v1/collection`. Bearer authentication; standard error envelope.

A **collection task** is a unit of field work: collect waste at a place (usually tied to a verified waste report), optionally with a vehicle, and record the weight actually collected.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /collection/tasks` | `collection:read` | Paginated list (`mine=true` for the caller's own) |
| `GET /collection/tasks/{id}` | `collection:read` | Task with assignment, status history and events |
| `POST /collection/tasks` | `collection:manage` | Create (`201`) |
| `POST /collection/tasks/{id}/assign` | `collection:manage` | Assign or re-assign an operator (and optional vehicle) |
| `POST /collection/tasks/{id}/start` | `collection:execute` | `assigned → in_progress` |
| `POST /collection/tasks/{id}/events` | `collection:execute` | Log `arrived`, `skipped`, `contaminated`, `delivered_to_facility` (`201`) |
| `POST /collection/tasks/{id}/complete` | `collection:execute` | `in_progress → completed` with the collected weight |
| `POST /collection/tasks/{id}/fail` | `collection:execute` | `assigned|in_progress → failed` with a reason |
| `POST /collection/tasks/{id}/cancel` | `collection:manage` | Cancel with a reason |
| `POST /collection/tasks/{id}/reschedule` | `collection:manage` | `failed → pending` with a new `due_at` |

Roles: collectors hold `collection:read|execute`; managers and administrators also hold `collection:manage`. Citizens have no access.

## Lifecycle

```
pending ──assign──▶ assigned ──start──▶ in_progress ──complete──▶ completed (terminal)
   │                  │ ▲  └─assign (re-assign)      │
   │                  │ └──────────────┘             ├──fail──▶ failed ──reschedule──▶ pending
   └─cancel─▶ cancelled (terminal) ◀─cancel──────────┘
```

Only the edges above exist; any other transition is `409 invalid_task_transition`. The edge check runs **before** the ownership check, so acting on a terminal task is `409` for everybody. Every change appends a row to the status history (`from_status`, `to_status`, actor, note).

## Who may act

Users holding only `collection:execute` can start, log events on, complete or fail a task **only while they are its active assignee** (`403` otherwise). Users with `collection:manage` may act for anyone.

## Creating and assigning

`TaskCreate`: `waste_report_id` (optional), `title`, `priority` (`low|normal|high|urgent`), `due_at`, `address_text`, `latitude`/`longitude` (both or neither), `destination_facility_id`, `notes`.

* A linked report must be `verified`: `409 report_not_verified`.
* A report can have **one open task** at a time: `409 report_has_open_task`.
* `due_at` cannot be in the past (`422`).
* The assignee must be an active user holding `collection:execute`: otherwise `422`.
* A vehicle must exist and be `available` or `in_service`: `409 vehicle_unavailable`.
* Re-assigning ends the previous assignment (`unassigned_at` is set) and records a history row.

## Completing

`POST /complete` body: `collected_weight_kg` (> 0, ≤ 100,000, 3 decimals), optional `destination_facility_id`, `notes`. In one transaction it:

1. writes a `collected` event carrying the authoritative weight,
2. moves the task to `completed`,
3. closes the linked report (`closed`),
4. awards reward points **once** to the reporter (`reward_points_per_kg` × weight, default 10 points per kg, configured by `REWARD_POINTS_PER_KG`; idempotent per task),
5. notifies the reporter, and
6. writes the audit entries.

Only **weights** are recorded. The API does not compute CO₂e or other environmental figures: there is no sourced coefficient set in the platform yet, so none are shown.

`collected` cannot be logged through `/events` (`422`).

## Listing

`GET /collection/tasks?page=1&page_size=25&status=assigned&priority=high&mine=true&assignee_id=…&waste_report_id=…&due_before=…&due_after=…&q=…&sort_by=due_at&order=asc`

`sort_by`: `created_at|due_at|priority|status`. `q` is a case-insensitive substring over title and address (max 100 characters; wildcards literal).

## Audit events

`collection_task.created`, `.assigned`, `.started`, `.event.<type>`, `.completed`, `.failed`, `.cancelled`, `.rescheduled`.
