# Authentication API

Base path: `/api/v1/auth`. Errors use the standard envelope (`docs/api/api-conventions.md`):
`{"error": {"code", "message", "details", "request_id"}}`. Design and threat model:
`docs/security/security-baseline.md`.

## Tokens

| Token | Form | Lifetime | Where it lives |
|---|---|---|---|
| Access token | signed JWT (HS256) | 15 min (`ACCESS_TOKEN_EXPIRE_MINUTES`) | Client memory; sent as `Authorization: Bearer <token>` |
| Refresh token | opaque 256-bit value | 14 days (`REFRESH_TOKEN_EXPIRE_DAYS`), rotated on every use | `ecomind_refresh` cookie: `HttpOnly`, `SameSite` (default `lax`), `Secure` when `REFRESH_COOKIE_SECURE=true`, `Path=/api/v1/auth` |

Responses that carry tokens send `Cache-Control: no-store`.

`refresh` and `logout` are authenticated by the cookie and therefore require the header
`X-CSRF-Protection: 1`; without it they return `403 forbidden`.

## Endpoints

### `POST /register` → `201`
Creates a `citizen` account and signs it in. Body: `{"email", "password", "full_name"}`; extra fields (for example `roles`) are rejected with `422`.

| Status | `error.code` | When |
|---|---|---|
| 409 | `email_already_registered` | Email exists (case-insensitive) |
| 422 | `weak_password` | Violates the password policy; `details[]` lists each reason |
| 422 | `validation_error` | Malformed email, blank name, over-long fields |
| 429 | `rate_limited` | More than 10 registrations from one address in an hour (`Retry-After`) |

### `POST /login` → `200`
Body: `{"email", "password"}`. Returns `AuthResponse` and sets the refresh cookie. For an account with two-factor authentication it returns an **`MfaChallenge`** instead (`{mfa_required: true, mfa_token, expires_in: 300}`), with no access token and no cookie; complete it with `POST /mfa/verify`. Clients tell the two apart by the `mfa_required` field.

| Status | `error.code` | When |
|---|---|---|
| 401 | `invalid_credentials` | Unknown email, wrong password or deactivated account (indistinguishable) |
| 429 | `rate_limited` | 5 failed attempts for this email, or 30 from this address, within 15 minutes (`Retry-After`) |

### Two-factor authentication (TOTP)

Details, threat model and limits: `docs/security/mfa.md`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /mfa/verify` | `mfa_token` in the body | Second sign-in step. Body `{mfa_token, code}` (6-digit code or recovery code). Returns `AuthResponse` and sets the cookie |
| `GET /mfa` | Bearer | `{enabled, pending_enrollment, enabled_at, recovery_codes_remaining}` |
| `POST /mfa/enroll` | Bearer | New secret, shown once: `{secret, otpauth_uri, issuer, digits, period_seconds}`. Inactive until confirmed. `409 mfa_already_enabled` if on |
| `POST /mfa/activate` | Bearer | Body `{code}`. Confirms enrolment; returns ten recovery codes once. `422 invalid_mfa_code`, `409 mfa_enrollment_not_started` |
| `POST /mfa/disable` | Bearer | Body `{password, code}` (code may be a recovery code). `204`. `401 invalid_credentials`, `422 invalid_mfa_code`, `409 mfa_not_enabled` |
| `POST /mfa/recovery-codes` | Bearer | Body `{password, code}`. Replaces all recovery codes; returns ten new ones once |

Second-step errors: `401 invalid_mfa_code` (wrong code, replayed code, expired or invalid `mfa_token`, deactivated account; deliberately one code), `429 rate_limited` after five wrong codes in 15 minutes. An administrator can remove a locked-out user's authenticator with `POST /api/v1/admin/users/{id}/reset-mfa`.

### `POST /refresh` → `200`
Cookie + CSRF header. Rotates the refresh token and returns a new `AuthResponse`.

| Status | `error.code` | When |
|---|---|---|
| 401 | `invalid_refresh_token` | Missing, unknown, expired or revoked; also a token rotated within the last 10 s (benign race: the cookie is **not** cleared) |
| 401 | `refresh_token_reused` | A rotated token was replayed later: the whole session family is revoked |
| 403 | `forbidden` | CSRF header missing |

### `POST /logout` → `204`
Cookie + CSRF header. Revokes the presenting device's session family and clears the cookie. Idempotent; never reveals whether the token was valid.

### `GET /me` → `200`
Bearer token. Returns `{id, email, full_name, roles[], permissions[]}` read fresh from the database.

### `POST /change-password` → `200`
Bearer token. Body: `{"current_password", "new_password"}`. Revokes **all** sessions, then starts a new one for this device (new cookie, new `AuthResponse`).
`401 invalid_credentials` (wrong current password, audited), `422 weak_password` (also when the new password equals the current one).

## `AuthResponse`
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "expires_in": 900,
  "user": {"id": "…", "email": "…", "full_name": "…", "roles": ["citizen"], "permissions": ["waste_reports:create", "…"]}
}
```

## Protected endpoints

Missing/invalid/expired token → `401` with `WWW-Authenticate: Bearer`. Valid token without the required permission → `403 forbidden` (the message never names the permission).
A deactivated user's tokens stop working immediately.

## Roles

| Role | Intended user | Highlights |
|---|---|---|
| `citizen` | Resident (default at sign-up) | Submit and see own reports, classify, sorting guide, own rewards and notifications |
| `collector` | Field collector / driver | View and work assigned collection tasks, routes, fleet and facilities |
| `facility_operator` | Processing facility staff | Recovery records, material passports, review classification |
| `manager` | Operations manager | Collection, fleet, routes, facilities, analytics, forecasts, anomalies, incidents, rewards |
| `administrator` | System administrator | Everything, including users, audit log and settings |

Source of truth: `backend/app/modules/users/rbac.py`.

## First administrator
```
cd backend
ECOMIND_ADMIN_PASSWORD='…' python -m app.cli create-admin --email admin@your-org.example --name "Site Admin"
```
