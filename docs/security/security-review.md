# Security review

Review date: 2026-10-20, on branch `arena/39c812ff-ecomind-ai` (PR #9). This is a self-review by the
developers using automated tools plus reading the code. It is **not** an independent penetration test and
nothing here certifies the system as secure. Controls are described in
[security-baseline.md](security-baseline.md); this file records what was checked, what was found and what
remains open.

## What was run

| Check | Command | Result |
|---|---|---|
| Frontend dependencies | `npm audit` (in `frontend/`) | 0 vulnerabilities |
| Backend dependencies | `pip-audit --skip-editable` (backend venv) | `cryptography 49.0.0` (PYSEC-2026-3552, PKCS#7 decryption oracle; the app only uses Fernet and HKDF, so it was not reachable) and the venv's own `setuptools 66.1.1` (build tooling, not a runtime dependency). **Fixed:** range widened to `cryptography>=43,<51`, tested with 50.0.2 (auth, MFA, unit and security suites pass); `pip-audit` then reports no `cryptography` finding. `setuptools` is not declared by the project |
| Static analysis | `bandit -r backend/app ml/common ml/waste_classification` | 13 findings, all Low severity, none Medium/High: `B105` on the token-type strings `"access"`/`"mfa_challenge"` (not passwords), `B311` on the seeded `random` used for deterministic route-improvement tie-breaking (not security), and `B404/B603/B607` on the training script's `git` calls (fixed argument lists, no shell, not reachable from the API) |
| Secrets in the repository | `git grep` for private-key headers and AWS/GitHub/Slack token shapes (outside `docs/`) | no matches. GitGuardian reports one "Generic Password" on the test `backend/tests/api/test_administration.py` (a throw-away test credential): a reviewed false positive that stays in history |
| Secrets in the client bundle | `grep` of `frontend/dist` | only UI labels such as "password"; no key material (`VITE_*` carries only the API base URL) |
| Every route protected | `backend/tests/security/test_route_inventory.py` (new) | 123 operations; exactly 7 are public (health, readiness, register, login, MFA verify, refresh, logout) and exactly 8 need only a signed-in user (own-account and model-info routes); every permission named by a route exists and is held by some role. A mutation (removing a route's permission dependency) made the test fail |
| Who may call what | `docs/security/route-permission-matrix.md` (generated, CI-checked) | the full method × path × permission × role table |
| Browser CSP | production build served with a strict CSP, real Chromium, 15 signed-in pages | 0 violations after the zod change below |

## Findings fixed in this review

1. **No security headers on the nginx locations.** `add_header` is not inherited into a `location` that
   sets its own, and both locations set `Cache-Control`, so `X-Content-Type-Options`, `X-Frame-Options` and
   `Referrer-Policy` were never actually sent. They are now repeated in each location, with a
   Content-Security-Policy (`default-src 'self'`, no inline script, no eval, `frame-ancestors 'none'`).
   `connect-src` allows any `https:` origin because the API origin is a build-time choice; narrow it when
   deploying. The nginx file itself has **not** been run in this sandbox (no nginx binary; Docker is
   unavailable); the policy was exercised by serving the same build with the same policy from a small
   Python server.
2. **zod probed `new Function('')`,** which a CSP without `unsafe-eval` reports as a violation (15 reports
   across the pages). The app now sets `z.config({ jitless: true })` before any schema exists
   (`frontend/src/app/zod-config.ts`, unit-tested). Behaviour was already safe (zod falls back), but the
   noise would have hidden real violations.
3. **API responses had no `X-Content-Type-Options`, `Referrer-Policy` or cache policy.** The request
   middleware now sets `nosniff`, `Referrer-Policy: no-referrer` and `Cache-Control: no-store` as defaults
   (endpoints that set their own value, such as the photo endpoints' `private, no-cache`, keep it).
   Tested on success, 401 and 404 responses.
4. `cryptography` upper bound (above).

## Verified controls (spot checks, not new work)

- Interactive API docs and the OpenAPI document are disabled when `ENVIRONMENT=production`
  (`app/main.py`).
- Startup fails on a weak or placeholder `SECRET_KEY`, and in production on insecure cookies or a wildcard
  CORS origin (`core/config.py`, tested).
- SQL goes through SQLAlchemy; the only raw statements are constant (`SELECT 1`, `alembic_version`, the
  UUID default, check-constraint text built from enum literals).
- Uploads are decoded, re-encoded and size-limited; storage keys are generated (baseline, file uploads).

## Open gaps (stated, not hidden)

- **Client address behind a proxy:** per-address limits use the peer address; production must configure
  trusted forwarded headers or every user shares the proxy's address.
- **No forced MFA** for any role; MFA is TOTP only. Rotating `SECRET_KEY` invalidates stored MFA secrets
  (recovery: administrator reset).
- **Account enumeration at registration:** `409 email_already_registered`.
- **Passwords:** a small denylist, not a breached-password corpus; no password reset or e-mail
  verification flow exists.
- **Uploads:** no antivirus scan; unattached uploads are not purged automatically.
- **Authorization subtleties:** incident photos need `waste_reports:create`; managers hold `users:read`.
  Both are documented design choices that an owner may want to change.
- **CSP `connect-src`** must be narrowed per deployment (above); `style-src 'unsafe-inline'` remains for
  React `style` attributes.
- **Dependencies:** the backend uses version ranges, not a lock file; no Dependabot or scheduled audit is
  configured. `pip-audit`, `npm audit` and `bandit` were run by hand once and are not CI gates.
- **Not done:** DAST/penetration testing, container image scanning, threat-model review by a second
  person, load testing.
