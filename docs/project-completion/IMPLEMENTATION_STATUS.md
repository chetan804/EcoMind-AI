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
| auth | models + migration | none | Missing (primitives exist: Argon2id, JWT, refresh hashing) |
| users / roles / permissions | models | none | Missing (no seed data) |
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
| audit | models | none | Missing |
| analytics | none | none | Missing (no models by design; to be query-based) |
| administration | none | none | Missing |
| health / ready | n/a | yes | Verified |

### Frontend screens (22 reference screens)

Only screens 01–04 exist. See `docs/ui/screen-inventory.md`. Screens 05–22: Missing.

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

(Appended per phase with exact commands and counts.)
