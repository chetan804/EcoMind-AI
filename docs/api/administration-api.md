# Administration API

Base path `/api/v1/admin`. User and role management, the audit log and non-secret system information.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /admin/users` | `users:read` | Users (`q` on email/name, `role`, `is_active`, `page`, `page_size`) |
| `GET /admin/users/{id}` | `users:read` | One user with roles |
| `POST /admin/users/{id}/reset-mfa` | `users:manage` | Remove a user's authenticator (`reason`); signs them out everywhere |
| `GET /admin/roles` | `users:read` | Roles with their permission codes and holder counts |
| `PUT /admin/users/{id}/roles` | `users:manage` | Replace a user's roles (`roles`, `reason`) |
| `POST /admin/users/{id}/deactivate` | `users:manage` | Deactivate (`reason`); revokes every refresh session |
| `POST /admin/users/{id}/activate` | `users:manage` | Reactivate (`reason`) |
| `GET /admin/audit-logs` | `audit:read` | Audit log, newest first (`action`, `entity_type`, `entity_id`, `actor_id`, `occurred_from`, `occurred_to`) |
| `GET /admin/system` | `settings:manage` | Non-secret runtime configuration, database revision, active model version |

Managers hold `users:read` (to see who can be assigned work) but not `users:manage`, `audit:read` or `settings:manage`; only administrators hold those.

## Rules

* **Reason required.** Every change takes a `reason` of 3–500 characters; it is stored in the audit row with the before and after values.
* **No self-service.** An administrator cannot change their own roles or active state (`409 self_modification_forbidden`); another administrator must.
* **Last administrator.** A change that would leave no active administrator is `409 last_administrator`. The active administrators are row-locked while this is checked, so two concurrent demotions cannot both succeed.
* **Unknown role** names are `422`. Roles are the five seeded system roles; creating custom roles is not offered.
* **Immediate effect.** Permissions are read from the database on every request, so a role change or deactivation applies to access tokens already issued. Deactivation also revokes all refresh sessions.
* **Idempotent.** Repeating a deactivate or activate that changes nothing writes no audit row.

## Audit log

Rows are append-only and never contain secrets or password hashes (`changes` is written by the services). Actions written by administration: `user.roles_changed`, `user.deactivated`, `user.activated`. Other modules write their own actions (for example `auth.logout`, `community_incident.resolved`).

## System information

Never includes the secret key, database URL or filesystem paths. It reports environment, log level, token lifetimes, cookie flags, CORS origins, storage backend, upload limit, reward points per kg, the database revision (`alembic_version`) and the active classification model version (or `null`).

## Not implemented

Creating users on behalf of others, password reset, email verification, custom roles, and editing settings through the API (they are environment variables). Users have an `mfa_enabled` flag; enrolment itself is in `docs/api/auth-api.md`.
