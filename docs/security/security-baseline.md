# Security baseline

Implemented controls are marked **✔**; the rest are requirements for the features that introduce them.

## Authentication strategy (decision)
- **Passwords:** Argon2id (`argon2-cffi`, library defaults), transparent rehash on login when parameters change. Minimum length and breach-list checks are defined with the sign-up feature. ✔ primitives (`core/security.py`, tested)
- **Access token:** signed JWT (HS256), 15 minutes by default (`ACCESS_TOKEN_EXPIRE_MINUTES`), claims `sub`, `type=access`, `iss`, `iat`, `exp`, `jti`. Decoding enforces an explicit algorithm allow-list, issuer, expiry and token type (rejects `alg=none`, tampering, wrong key). Sent as `Authorization: Bearer`; kept **in memory** by the SPA, never in `localStorage`. ✔ primitives
- **Refresh token:** opaque 256-bit random value in an **HttpOnly, Secure, SameSite** cookie scoped to `/api/v1/auth`. Only its SHA-256 digest is stored (`auth_sessions.token_hash`). Each use **rotates** the token in the same `family_id`; presenting an already-rotated token revokes the whole family (theft detection). Expiry `REFRESH_TOKEN_EXPIRE_DAYS` (14). Logout and password change revoke sessions. ✔ schema and primitives; endpoints pending
- **Why not server sessions only / long-lived JWTs:** short-lived stateless access tokens keep API checks cheap; revocable hashed refresh sessions allow logout and compromise response.
- **CSRF:** the refresh endpoint is the only cookie-authenticated endpoint; it requires `SameSite` cookies plus a custom header / JSON content type and allowed-origin check. All other endpoints use bearer tokens and are not CSRF-prone.
- **Authorization:** deny by default; permission strings `<resource>:<action>` granted via roles; checked server-side in dependencies/services (`core/permissions.py`). The frontend hides UI by permission for usability only. ✔ primitive

## Configuration and secrets
- All secrets from environment variables, validated at startup (`core/config.py`): `SECRET_KEY` ≥ 32 chars and not the template placeholder; production requires `REFRESH_COOKIE_SECURE=true` and no `*` in CORS origins. ✔ tested
- `.env` files are git-ignored; templates contain placeholders only; `scripts/quality/check_env_templates.py` fails CI on real-looking values or tracked `.env` files. ✔
- `VITE_*` variables are public: never put secrets there. Docker images contain no secrets; `.dockerignore` excludes `.env*`. ✔
- Compose binds PostgreSQL to `127.0.0.1` only; development passwords are generated per developer (`make env`). ✔

## Transport and browser
- TLS terminates in front of the backend and frontend (deployment responsibility). The nginx image sets `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`. ✔
- CORS restricted to configured origins. ✔ tested
- A Content-Security-Policy is defined when the frontend deployment host is chosen (pending).

## Input handling
- Pydantic validation on all inputs; uploads limited by `MAX_UPLOAD_BYTES`, type allow-list (JPEG/PNG/WebP), pixel-count limit against decompression bombs, EXIF orientation applied, content hashed. ✔ image validation in `ml/common/preprocessing`; upload endpoint pending
- Stored filenames are generated keys, never user-supplied paths. SQL only through SQLAlchemy (parameterized).

## Errors, logging, audit
- Errors use one envelope; unhandled exceptions return a generic message and are logged with a request id. ✔ tested
- Logs never contain passwords, tokens, secrets or full request bodies. JSON logging available. ✔ (formatter); discipline enforced in review
- Audit log (`audit_logs`) is append-only; `changes` must exclude secrets. Schema ✔; writing entries pending.

## Dependencies and CI
- Dependencies pinned by lockfile on the frontend (`package-lock.json`); the backend uses version ranges (a lock/constraints file is a recommended follow-up). Enable Dependabot/`pip-audit`/`npm audit` in CI when the repository is public or has Advanced Security (follow-up).
- Containers run the backend as a non-root user. ✔

## Reporting
See `/SECURITY.md`.
