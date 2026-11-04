# Role requests API

Base path `/api/v1/access-requests`. Public registration always creates a **citizen**. A signed-in person who needs an operational role asks for it here and an administrator decides. Nobody can obtain a privileged role by choosing it, and the `administrator` role cannot be requested (it is created with `python -m app.cli create-admin`, or by another administrator under Settings, Users).

| Method and path | Permission | Purpose |
|---|---|---|
| `POST /access-requests` | signed in | Ask for `collector`, `facility_operator` or `manager` with a reason (20 to 2000 characters) and an optional organisation (`201`). Changes no role |
| `GET /access-requests/mine` | signed in | The caller's own requests, newest first |
| `POST /access-requests/{id}/withdraw` | signed in | Withdraw the caller's own pending request; anyone else's id answers `404` |
| `GET /access-requests` | `users:manage` | All requests, filter `status_filter` and `role`, paginated |
| `POST /access-requests/{id}/decision` | `users:manage` | `{"approve": true\|false, "note": "..."}`. Approving **adds** the role next to the existing ones; rejecting needs a note |

## Rules

* One pending request per person (database unique index): a second one answers `409 role_request_pending`.
* Asking for a role already held answers `409 role_already_held`.
* A decided or withdrawn request cannot be decided again (`409 role_request_decided`).
* An administrator cannot decide their own request (`403`).
* Every step is audited (`access_request.created`, `.approved`, `.rejected`, `.withdrawn`) and the requester gets an in-app notification on a decision.
* Two-step sign-in is still enforced by the existing policy for the manager role in production.

Tests: `backend/tests/api/test_access_requests.py`.
