# Security baseline

Implemented controls are marked **✔**; the rest are requirements for the features that introduce them.

## Authentication strategy (decision)
- **Passwords:** Argon2id (`argon2-cffi`, library defaults), transparent rehash on login when parameters change. **Policy (implemented, `modules/auth/policy.py`):** 12–128 characters, no composition rules, rejected if it is on a small embedded common-password list, is trivially repetitive, or contains the email local part or the user's name. This is a *basic* denylist, **not** a breached-password corpus check (follow-up). ✔ tested
- **Access token:** signed JWT (HS256), 15 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES`), claims `sub`, `type=access`, `iss`, `iat`, `exp`, `jti`. Decoding enforces an explicit algorithm allow-list, issuer, expiry and token type (rejects `alg=none`, tampering, wrong key). Sent as `Authorization: Bearer`; kept **in memory** by the SPA, never in `localStorage`. ✔ primitives
- **Refresh token:** opaque 256-bit random value in an **HttpOnly, Secure, SameSite** cookie scoped to `/api/v1/auth`. Only its SHA-256 digest is stored (`auth_sessions.token_hash`). Each use **rotates** the token in the same `family_id`; presenting an already-rotated token revokes the whole family (theft detection). Expiry `REFRESH_TOKEN_EXPIRE_DAYS` (14). Logout revokes the presenting device's family; password change revokes **all** sessions and starts a fresh one. A rotated token replayed within `REFRESH_REUSE_GRACE_SECONDS` (10 s) is refused *without* revoking the family and *without* clearing the cookie (two tabs refreshing at once share one cookie jar, so clearing would sign the user out); a replay after the grace window revokes the family. Refresh rows are locked (`SELECT … FOR UPDATE`) so concurrent use of one token has exactly one winner. ✔ endpoints and tests (`backend/tests/api/test_auth_*.py`)
- **Why not server sessions only / long-lived JWTs:** short-lived stateless access tokens keep API checks cheap; revocable hashed refresh sessions allow logout and compromise response.
- **CSRF:** `refresh` and `logout` are the only cookie-authenticated endpoints. They require the custom header `X-CSRF-Protection: 1` (a cross-site page cannot add a custom header without a CORS preflight, which only configured origins pass) on top of a `SameSite` cookie scoped to `/api/v1/auth`. **Decision:** the earlier plan also called for an `Origin` allow-list check; it was dropped because behind the dev proxy the `Origin` is the frontend while the request host is the backend, so the check would need per-deployment configuration without adding protection beyond the custom header (OWASP's custom-request-header defence). All other endpoints use bearer tokens and are not CSRF-prone. ✔ tested
- **Authorization:** deny by default; permission strings `<resource>:<action>` granted via roles (`modules/users/rbac.py`, seeded by migration `0002`, drift-guarded by a test); enforced server-side by `require_permissions(...)` (`modules/auth/dependencies.py`). Roles and permissions are **re-read from the database on every request** (not embedded in the token), so deactivating a user or removing a role takes effect immediately instead of at token expiry. Self-registration can only produce `citizen` (the schema rejects extra fields such as `roles`); other roles are assigned by an administrator; the first administrator is created with `python -m app.cli create-admin`. The frontend hides UI by permission for usability only. ✔ tested (`backend/tests/security/test_authorization.py`)
- **Brute-force limits:** failed logins are limited per email (5 per 15 min) and per source address (30 per 15 min); registrations per address (10 per hour). Counters are derived from the append-only `audit_logs` table so they are shared by all workers **without Redis**; a successful login resets the per-email count; the limit applies equally to unknown emails (so the lock does not reveal which emails exist); locked attempts are not recorded, so a lock cannot be extended by hammering. Trade-off: an attacker can lock a victim's *sign-in* for up to 15 minutes (a temporary denial of service); credentials stay protected. ✔ tested
- **Account enumeration:** sign-in failures (unknown email, wrong password, deactivated account) return one identical error and a dummy Argon2 verification equalises timing. **Known gap:** registration returns `409 email_already_registered`, which does reveal that an address is registered; mitigated only by the per-address registration limit.
- **Client-side token handling:** the access token lives only in JavaScript memory (never `localStorage`/`sessionStorage`/cookies); `localStorage` holds a single non-secret *hint* that a session probably exists. The refresh token is never visible to JavaScript. The query cache is cleared whenever a signed-in session ends. ✔ unit and e2e tested
- **Client address behind a proxy:** per-address limits use the direct peer address (`request.client.host`); `X-Forwarded-For` is deliberately not trusted because any client can forge it. Behind a reverse proxy (including the Compose frontend container) every user therefore shares the proxy's address until the ASGI server is configured to trust the proxy's forwarded headers. **Production must configure this** before the per-address limits are meaningful.

## File uploads (waste-report photos)

Implemented in `waste_reports/images.py` and `integrations/file_storage/local.py`; behaviour and limits are in [docs/api/waste-reports-api.md](../api/waste-reports-api.md). Controls, each covered by a test:

- **Never trust the client:** declared content type and file name are ignored; the format is detected by decoding (JPEG/PNG/WebP only; SVG, GIF, PDF, empty and truncated files are refused).
- **Re-encode every image**, which strips EXIF/GPS (citizen location privacy), trailing data and polyglot payloads.
- **Resource limits:** byte cap enforced while streaming, 40-megapixel decoded cap (decompression bomb), 32 px minimum side, 20 unattached uploads per user.
- **No path control:** storage keys are generated (`<hex>/<uuid>.<ext>`) and re-validated against an allow-list on every operation, resolved paths must stay inside the storage root (symlink escape tested), writes are atomic and files are 0600.
- **Safe delivery:** `nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`, generated `Content-Disposition`, `Cache-Control: private`.
- **Authorization:** only the uploader or `waste_reports:read_all`; others get 404 (no probing).
- **Known gaps:** no antivirus scan (images are re-encoded instead); no automated purge of unattached uploads; storage is a local volume (single node); orphan files can remain if the process dies between writing a file and committing its row.

## Configuration and secrets
- All secrets from environment variables, validated at startup (`core/config.py`): `SECRET_KEY` ≥ 32 chars and not the template placeholder; production requires `REFRESH_COOKIE_SECURE=true` and no `*` in CORS origins. ✔ tested
- `.env` files are git-ignored; templates contain placeholders only; `scripts/quality/check_env_templates.py` fails CI on real-looking values or tracked `.env` files. ✔
- `VITE_*` variables are public: never put secrets there. Docker images contain no secrets; `.dockerignore` excludes `.env*`. ✔
- Compose binds PostgreSQL to `127.0.0.1` only; development passwords are generated per developer (`make env`). ✔

## Transport and browser
- TLS terminates in front of the backend and frontend (deployment responsibility). The nginx image sets `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`. ✔
- CORS restricted to configured origins. ✔ tested
- The nginx image sends `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` and a Content-Security-Policy on every location; the API sends `nosniff`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store` by default. `connect-src` must be narrowed to the deployment's API origin. Details and the verification method: [security-review.md](security-review.md). ✔ tested (API headers); the nginx file itself is untested here.
- Every route's required permission is listed in the generated [route-permission-matrix.md](route-permission-matrix.md) and guarded by `tests/security/test_route_inventory.py`.

## Input handling
- Pydantic validation on all inputs; uploads limited by `MAX_UPLOAD_BYTES`, type allow-list (JPEG/PNG/WebP), pixel-count limit against decompression bombs, EXIF orientation applied, content hashed. ✔ image validation in `ml/common/preprocessing`; upload endpoint pending
- Stored filenames are generated keys, never user-supplied paths. SQL only through SQLAlchemy (parameterized).

## Errors, logging, audit
- Errors use one envelope; unhandled exceptions return a generic message and are logged with a request id. ✔ tested
- Logs never contain passwords, tokens, secrets or full request bodies. JSON logging available. ✔ (formatter); discipline enforced in review
- Audit log (`audit_logs`) is append-only, enforced by a database trigger since migration 0017 (UPDATE and DELETE fail; only detaching a removed user's `actor_id` is allowed); `changes` must exclude secrets. ✔ written for register, login (success/failure, with a SHA-256 pseudonym of the email, never the clear address), logout, refresh-reuse detection, password change (success/failure) and CLI admin creation. Other modules add their events as they are built.

## Dependencies and CI
- Dependencies pinned by lockfile on the frontend (`package-lock.json`); the backend uses version ranges (a lock/constraints file is a recommended follow-up). Enable Dependabot/`pip-audit`/`npm audit` in CI when the repository is public or has Advanced Security (follow-up).
- Containers run the backend as a non-root user. ✔

## Reporting
See `/SECURITY.md`.
