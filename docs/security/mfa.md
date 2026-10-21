# Two-factor authentication (TOTP)

**Status:** implemented in the backend (migration `0008`, `app/modules/auth/{totp,mfa}.py`). Optional per user by default; in production administrators and managers must enrol (see "Required roles").

## What it is

Time-based one-time passwords as in RFC 6238 (HOTP, RFC 4226): HMAC-SHA1, 6 digits, 30-second steps, which is what Google Authenticator, Microsoft Authenticator, Aegis, 1Password and similar apps support. `tests/unit/test_totp.py` checks the implementation against the RFC 4226 appendix D and RFC 6238 appendix B vectors.

## Flow

1. **Enrol** (`POST /auth/mfa/enroll`): the server creates a 160-bit secret, stores it **encrypted**, and returns the secret and an `otpauth://` URI once. Nothing changes at sign-in yet.
2. **Confirm** (`POST /auth/mfa/activate`): the user types a code from the app. Only then is the factor active, so a failed scan cannot lock the user out. Ten recovery codes are returned once.
3. **Sign in**: `POST /auth/login` checks the password and returns an `MfaChallenge` (5-minute signed token, no session). `POST /auth/mfa/verify` takes that token and a code and only then issues the access token and refresh cookie.
4. **Manage**: disabling or re-issuing recovery codes needs the password **and** a current code, so a stolen access token cannot weaken the account.

## Protections and their tests (`tests/api/test_mfa.py`)

| Risk | Control |
|---|---|
| Database leak exposes secrets | Secrets are Fernet-encrypted with a key derived from `SECRET_KEY` by HKDF-SHA256 (a different key from the JWT signing use); recovery codes are stored only as HMAC-SHA256 hashes |
| Captured code replayed | The last accepted time step is stored per factor; a step is accepted once, and earlier steps are refused |
| Clock drift | One step either side of the current one is accepted, no more |
| Brute force | Five wrong codes per user per 15 minutes, then `429` with `Retry-After` (derived from the audit log, so it works across workers) |
| Challenge token abused as an access token | It carries `type=mfa_challenge`; the access-token decoder rejects it. Tokens for users without MFA, deactivated users, expired, forged or access tokens are all refused with the same `invalid_mfa_code` |
| Recovery code reuse | One atomic `UPDATE ... WHERE used_at IS NULL`, so concurrent use of a code succeeds once |
| Account enumeration | A wrong password never reaches the second step and never mentions MFA |
| Non-ASCII digits | Rejected before comparison (a unit test covers this; it was a real bug caught during development) |

Audit events: `auth.mfa_enrolment_started`, `auth.mfa_enabled`, `auth.mfa_succeeded`, `auth.mfa_failed` (with a reason, never the code), `auth.mfa_disabled`, `auth.mfa_recovery_codes_regenerated`, and `user.mfa_reset` by an administrator.

## Operations

* **Lost device and recovery codes:** an administrator calls `POST /admin/users/{id}/reset-mfa` with a reason; the user is signed out everywhere and can enrol again. Administrators cannot reset their own.
* **Rotating `SECRET_KEY`** invalidates every stored authenticator secret and recovery-code hash, and signs out everyone anyway. Affected users get `409 mfa_secret_unreadable` and need an administrator reset. Plan rotation as a maintenance event.
* **Dependency:** `cryptography` (Fernet, HKDF). Everything else is standard library.

## Required roles

`MFA_REQUIRED_ROLES` (comma-separated role names) lists the roles that must use two-step verification. Unset or blank it resolves to `administrator,manager` when `ENVIRONMENT=production` and to nobody otherwise, so local and CI stacks stay usable without an authenticator; `none` is the explicit opt-out, and an unknown role name stops the application at startup.

A person holding any listed role who has not completed enrolment can still sign in, but the server answers every endpoint except the account and two-step ones (`/auth/*`, which is how they enrol) with `403 mfa_enrollment_required`, including the signed-in-only `GET /classification/model`. The check reads the database on every request, so it cannot be avoided by keeping an old token, by starting but not confirming an enrolment, or by holding a second, unrestricted role. `GET /auth/me` and the sign-in response carry `mfa_enrollment_required`, and the web app sends such a person to Settings, Security with an explanation; the restriction lifts the moment the code is confirmed. While a listed role is held, `POST /auth/mfa/disable` is refused with `409 mfa_required_for_role`. Administrators who reset someone's factor (`reset-mfa`) put that person back in the enrolment-only state.

Tests: `backend/tests/api/test_mfa_enforcement.py` (nine cases; removing the check or the disable refusal fails them), `tests/unit/test_config.py`, and `frontend/tests/integration/security.test.tsx`.

## Limitations

* TOTP only: no WebAuthn/passkeys, SMS or email codes.
* The requirement covers roles, not individual accounts, and only TOTP satisfies it; a locked-out required user is reset by another administrator (`reset-mfa`) and must enrol again before doing anything else.
* Existing refresh sessions stay valid when MFA is switched on; the user can sign out other devices by changing the password.
* Recovery codes are shown once and cannot be retrieved; a user who loses them re-issues new ones while still signed in.
