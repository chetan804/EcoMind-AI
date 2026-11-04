# Role requests (`access_requests`)

How a person obtains an operational role without ever self-assigning one. Public registration always yields `citizen`;
a signed-in person may *request* `collector`, `facility_operator` or `manager`, and an administrator approves or rejects.
`administrator` cannot be requested (it is created with `python -m app.cli create-admin` or by another administrator).

**Status:** implemented (create, list own, withdraw, admin list, approve/reject, audit, notification). See `docs/api/`.

## Ownership
- **Tables owned:** `role_requests`
- **Files present:** `models.py`, `constants.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users` (roles), `audit`, `notifications`
- Other modules must use this module's `service.py` to change its data; never write to its tables directly.

## API
`/api/v1/access-requests`, registered in `app/api/v1/router.py`.
- `POST /` and `GET /mine`, `POST /{id}/withdraw`: any signed-in person, own requests only (someone else's id answers 404).
- `GET /` and `POST /{id}/decision` need `users:manage` (administrators only).

## Rules
One pending request per person (database unique index); a person who already holds the role cannot ask again; nobody decides
their own request; rejection needs a reason; approval adds the role and keeps the existing ones; the requester is notified.

## Tests
`backend/tests/api/test_access_requests.py`. Run: `make test-backend`.
