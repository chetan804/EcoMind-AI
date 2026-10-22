# Security review

Review date: 2026-10-20, on branch `arena/39c812ff-ecomind-ai` (PR #9). *Snapshot: figures below (for example 123 operations) are those of that review; the current route inventory (168 operations) is in [`docs/security/route-permission-matrix.md`](route-permission-matrix.md) and the later checks are in `docs/project-completion/REQUIREMENTS_CLOSURE_REPORT.md`.* This is a self-review by the
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
- **Passwords:** a small denylist, not a breached-password corpus. Password reset and e-mail verification
  exist (see "Supply chain and account recovery" below) but need a configured, tested mail server.
- **Uploads:** no antivirus scan; unattached uploads are not purged automatically.
- **Authorization subtleties:** incident photos need `waste_reports:create`; managers hold `users:read`.
  Both are documented design choices that an owner may want to change.
- **CSP `connect-src`** must be narrowed per deployment (above); `style-src 'unsafe-inline'` remains for
  React `style` attributes.
- **Dependencies:** now hash-locked and audited in CI (see "Supply chain and account recovery" below);
  base images are tagged, not digest-pinned.
- **Not done:** DAST/penetration testing, container image scanning, threat-model review by a second
  person, load testing.

## Maps and tracking (added 2026-10-21)

- **Keys.** The browser key (`VITE_GOOGLE_MAPS_API_KEY`) is public by design; the control is the Google Cloud restriction (HTTP referrer plus Maps JavaScript API only). The server key (`GOOGLE_MAPS_SERVER_API_KEY`) is read only by the backend, sent in the `X-Goog-Api-Key` header (never in a URL), held as a `SecretStr`, never logged and never returned in a response; a unit test asserts it is not in the request URL. A scan of the production bundle found no `AIza` key material (placeholders are empty everywhere).
- **CSP.** `deployment/docker/nginx.conf` adds the hosts Google documents for the Maps JavaScript API (script, style, image, connect, frame, font, worker) but still no `'unsafe-eval'`. The earlier "0 violations on 20 routes" result predates this change and the live Maps check is **pending** (needs a key and network access to Google). Re-run the CSP check with a key; if the map needs `'unsafe-eval'`, record that here as an accepted widening.
- **Authorization.** Position ingestion requires `fleet:track` and the caller must be assigned to the vehicle; imports need `fleet:manage` and cannot be recent; the simulator has its own permission and endpoints, stays separate from real data and is disabled by default in production. Collectors read only their own vehicles; collection tracking is for managers and the assignee. All covered by `backend/tests/api/test_tracking.py` and the generated route matrix (`route-permission-matrix.md`).
- **Privacy.** Positions are personal data about a driver's movements. Only an authorised, assigned account can write them; retention defaults to 90 days (`purge-location-events`); sharing is started by the collector and stops when the tab closes. Map labels and URLs carry no reporter identity or free text, and the directions link contains only a facility's public coordinates. A privacy notice and legal basis for tracking staff are the operator's responsibility.
- **Residual risks.** No per-device credentials (a tracker must use a collector account); polling load is proportional to open fleet screens; the Routes API is a billable dependency (budget alerts recommended); Google scripts run in the page, so the key restrictions and CSP are the only containment.

## Offline map and optional routing (added 2026-10-21)

- **Offline map CSP check (local, real Chromium, production build).** The `/fleet` map (MapLibre, PMTiles over
  Range requests, blob/own-origin worker, vendored fonts and sprites) was loaded with the exact CSP string from
  `deployment/docker/nginx.conf` applied to the document: 0 `securitypolicyviolation` events and no console
  errors; a negative control with `worker-src 'none'` did report the worker violation, so the check can fail.
  The map needs no host beyond `'self'` (no Google host), and still no `'unsafe-eval'`. The check used the Vite
  preview server with the header injected by the test browser, **not nginx** (none available): the nginx
  `/map-assets/` location is untested until CI builds the image and a real deployment is exercised.
- **Third parties.** The default provider sends nothing to third parties from the browser. Map data is an
  OpenStreetMap snapshot (ODbL, attribution displayed).
- **OSRM adapter.** Operator-set base URL only (http/https, no credentials/query/fragment, validated at
  startup), no redirects followed, 5 MB response cap, nothing stored, off by default. Run OSRM on a private
  network; do not expose it publicly. Tested with a mocked transport only.
- **Static analysis.** After this change `bandit -r backend/app -ll` reported one Medium (B310 on the Google
  Routes `urlopen`, a constant https URL; a false positive that the added scheme guard and a `nosec B310` with
  its reason now document); the earlier "13 Low, none Medium/High" figure predates the Routes adapter.

## Supply chain and account recovery (added 2026-10-22)

**Supply chain** (`docs/operations/dependency-management.md`)

- Python installs come from hash-verified universal lock files (`backend/requirements*.lock`, `ml/requirements-dev.lock`) in CI and the backend image; `make check-locks` fails CI when `pyproject.toml` and the locks disagree.
- Every GitHub Action is pinned to a commit SHA and the runner is `ubuntu-24.04`, not `ubuntu-latest`.
- The **Security** workflow (push, pull request, weekly) fails on any `pip-audit` finding in the backend or ML locks, on high or critical `npm audit` findings (frontend and e2e, dev dependencies included) and on bandit findings of medium severity or higher. At the time of writing all three were clean (0 vulnerabilities, 0 findings). The weekly run exists because that is a point-in-time statement. CodeQL (`security-extended`) runs for Python and JavaScript/TypeScript.
- **Gaps:** base images are not digest-pinned (registry unreachable from the build sandbox), no container image scan, no DAST, no automated licence review of transitive packages.
- **Secret scanner finding:** the GitGuardian "Generic Password" alert on `backend/tests/api/test_administration.py` was a word list in a test; the test now uses one regular expression. The alert on the earlier commit remains in history and must be dismissed in the GitGuardian dashboard (owner action).

**Account recovery** (`docs/operations/account-recovery.md`)

- One-time, 256-bit, hashed, expiring links; a newer link replaces older ones; the token travels in the URL fragment; the answers of both request endpoints are identical for every address; limits per address and per IP; a reset revokes all sessions, clears the lockout, keeps two-factor authentication and sends a notice; audit rows hold digests, never addresses or tokens.
- Attack surface added: four public endpoints. Limits come from the audit log (shared across workers). The `console` and `memory` e-mail backends are refused in production, because the console backend writes links to the log.
- **Residual risks:** e-mail is only as secure as the mailbox (that is why 2FA is not bypassed); no CAPTCHA, so a determined attacker can still fill a victim's inbox with up to three messages an hour; delivery through a real provider is untested here.
