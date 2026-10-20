# EcoMind AI — Implementation Status

Single source of truth for what is built, what is verified, and what is not.
Updated as work lands. Nothing here is claimed without evidence listed in the
**Evidence** column or in the "Verification log" section.

**Status vocabulary**

| Status | Meaning |
|---|---|
| Verified | Implemented and covered by automated tests that were run and passed |
| Unverified | Implemented, but not covered by an automated run yet |
| Partial | Some of the behaviour exists; gaps are listed |
| Simulated | Visible UI backed by labelled demo data, not a real backend |
| Missing | Not started |
| Blocked | Cannot be completed in this environment; reason given |

## 1. Starting baseline (Phase A audit)

- Base: `main` @ `b5e858a` (merge of PR #5). No open PRs. CI on that commit: Frontend CI success, Quality gates success (Backend CI is path-filtered and did not run).
- Working branch: `arena/4746886a-ecomind-ai`.
- Baseline suites, run locally before any change on this branch:

| Suite | Result |
|---|---|
| Backend pytest (real PostgreSQL 16.2) | 66 passed |
| `alembic upgrade head` from empty + `alembic check` | clean, no drift |
| Frontend vitest | 78 passed (12 files) |
| Frontend ESLint + `tsc -b` | clean |
| ML pytest | 7 passed |
| Contract tests | 5 passed |
| `check_structure.py`, `check_env_templates.py` | OK |

**Audit finding (the important one):** the repository is a *foundation*, not a working
application. The backend has a 29-table schema and security primitives, but
`api/v1/router.py` is empty — there are **no business endpoints**. The frontend has four
screens, of which only the sign-in form shape, the landing page, a demo-data dashboard
and a "not connected" classification page exist. `ml/` contains image preprocessing only:
no dataset, no training code, no model.

## 2. Capability matrix

### Backend modules

| Module | Schema | Endpoints | Status |
|---|---|---|---|
| auth | models + migration | register, login, refresh, logout, change-password, me | **Verified** (48 backend tests incl. concurrency + mutation checks; e2e) |
| users / roles / permissions | models + seed migration `0002` | none (no user-management API yet) | **Partial**: RBAC seeded and enforced (38 permissions, 5 roles, drift-guard test); first admin via CLI; no user-admin endpoints |
| audit | models | written by auth events; **no read endpoint yet** | **Partial** |
| waste_reports + media | models | none | Missing |
| classification | models | none | Missing (no model artifact exists) |
| collection | models | none | Missing |
| facilities | models | none | Missing |
| fleet | models | none | Missing |
| route_planning | models | none | Missing |
| sorting_guide / materials | models | none | Missing |
| circular_economy | models | none | Missing |
| material_passports | models | none | Missing |
| community_incidents | models | none | Missing |
| rewards | models | none | Missing |
| notifications | models | none | Missing |
| forecasting | models | none | Missing (no trained model) |
| anomaly_detection | models | none | Missing |
| analytics | none | none | Missing (no models by design; to be query-based) |
| administration | none | none | Missing |
| health / ready | n/a | yes | Verified |

### Frontend screens (22 reference screens)

Screens 01–04 exist; **02 (sign-in/up) is now wired to real authentication and sign-out exists**. 01 landing is static; 03 dashboard still shows labelled demonstration data; 04 classification still shows "not connected". Screens 05–22: Missing. See `docs/ui/screen-inventory.md`.

### ML

| Area | Status |
|---|---|
| Image preprocessing | Verified (7 tests) |
| Waste-image dataset | Blocked — see Blockers |
| Classification training/eval/inference | Missing |
| Forecasting, anomaly detection | Missing |

## 3. Blockers and environment limits (known at start)

- **No waste-image dataset is reachable.** The sandbox can reach only github.com, codeload,
  api.github.com, registry.npmjs.org, pypi.org and files.pythonhosted.org. TrashNet/TACO and
  similar are hosted elsewhere. Consequence: no classification model will be trained here and
  none will be claimed. The inference path, registry and "no active model" state are still built.
- Docker is not available in the sandbox; Compose is validated by schema and CI only.
- No deployment target or credentials: nothing will be deployed.

## 4. Verification log

### Phase B — authentication, RBAC, protected routes (this branch)

Commits: `df0938f` (backend) + the frontend/e2e/docs commit that follows it on this branch.

Migration: `0002_seed_roles_permissions` (data only; no schema change). Verified: `alembic upgrade head` from empty, downgrade to `0001` and re-upgrade, and `alembic check` reports no drift.

| Check | Command (from the directory shown) | Result |
|---|---|---|
| Backend lint/format/types | `cd backend && ruff check . && ruff format --check . && mypy` | clean (115 source files) |
| Backend tests, real PostgreSQL 16.2 | `cd backend && pytest` | **114 passed** (66 baseline + 48 new) |
| Mutation checks (deliberate regressions) | edit code, run `pytest tests/api tests/security -x` | 5/5 detected: reuse-revocation removed, lockout disabled, active-user check removed, CSRF guard disabled, distinguishable login error |
| Frontend lint / types | `cd frontend && npm run lint && npx tsc -b` | clean |
| Frontend unit + integration | `cd frontend && npx vitest run` | **127 passed** (78 baseline + 49 new), 15 files |
| Frontend production build | `cd frontend && npm run build` | succeeds; entry chunk 254.74 kB (was 253.49) |
| E2E against live backend + PostgreSQL + Vite | `cd tests/e2e && npx playwright test --workers=4` | **18 passed** (11 baseline-equivalent + 5 new auth journeys + 2 system-status); audit trail showed exactly 1 registration despite 4 parallel workers |

Defects found by testing during this phase (all fixed, none hidden):
1. Failed-refresh cookie clearing was lost because FastAPI discards headers set on the injected `Response` when an exception propagates (caught by `test_unknown_refresh_token_is_rejected_and_cookie_cleared`). The router now builds the error response itself.
2. Clearing the cookie on a benign refresh race would have signed the user out (tabs share one cookie jar); the race case is now a distinct error that leaves the cookie alone.
3. `mypy` as CI runs it (bare `mypy`, includes tests) found 5 typing errors my narrower local run missed.
4. e2e used the reserved domain `@example.test`, which the email validator correctly rejects; switched to `example.org`.
5. The e2e fixture logged in before registering, which on a fresh DB recorded failed logins and tripped the brute-force lockout (429); it now registers first.

Known limitations of this phase (also in `docs/security/security-baseline.md`):
- No MFA, password reset, email verification, or social sign-in (buttons stay disabled, labelled unavailable).
- Registration reveals whether an email is registered (409).
- Per-address limits use the direct peer address; behind a proxy they are shared until the ASGI server is configured to trust the proxy.
- Password policy is a length rule plus a small denylist, not a breached-password corpus check.
- Docker/Compose could not be run in this sandbox; Compose cookie configuration was checked statically only.
- CI results for this branch are not yet known (see the final report).
