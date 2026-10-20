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
| waste_reports + media | models + migration `0003` (idempotency) | create (idempotent), list/filter/search/sort, detail, review workflow, photo upload/download | **Verified locally (backend only)**: 90 tests incl. races and mutation checks; **no UI yet** |
| classification | models + migration `0004` | model status, model registry/activation, predict, get/list, one-time review | **Verified locally**: 34 backend tests incl. a real-artifact parity test and 7/7 mutation checks; real model served end to end in a browser (see Phase D). UI wired. |
| collection | models | none | Missing |
| facilities | models | list/filter/search/sort, detail, create, partial update (no delete by design) | **Verified locally (backend only)**: 32 tests; **no UI yet** |
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

Screens 01–04 exist; **02 (sign-in/up) is now wired to real authentication and sign-out exists**. 01 landing is static; 03 dashboard still shows labelled demonstration data; **04 classification is now wired to the real API** (upload, prediction, calibrated confidence, needs-review state, review form for permitted roles). Screens 05–22: Missing. See `docs/ui/screen-inventory.md`.

### ML

| Area | Status |
|---|---|
| Image preprocessing | Verified (7 tests) |
| Waste-image dataset | **Resolved**: TrashNet (MIT) is fetched from GitHub; manifest `datasets/manifests/trashnet-1.0.yaml` |
| Classification training/eval/inference | **Verified (candidate model 1.0.0)**: deterministic pipeline, report, model card, 36 ML tests; see Phase D |
| Forecasting, anomaly detection | Missing |

## 3. Blockers and environment limits (known at start)

- **Dataset (resolved in Phase D).** The sandbox reaches only github.com, codeload, api.github.com, registry.npmjs.org, pypi.org and files.pythonhosted.org, so HuggingFace/TACO/GCS are unreachable. TrashNet (MIT) lives in a GitHub repository, and an ImageNet-pretrained TFLite backbone (Apache-2.0) lives in `google-coral/test_data`; both are fetched at pinned commits with SHA-256 verification. Limits that remain: TrashNet is studio photography of six classes, so field accuracy is unmeasured and organic/e-waste are not covered.
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

**CI on PR #6, head `46bb072` (from the GitHub check-runs API, not inferred):**

| Result | Checks |
|---|---|
| success (all 9 project jobs, on both the push and pull_request runs) | Backend: Lint and type-check; Tests (Python 3.11, PostgreSQL 16); Tests (Python 3.12, PostgreSQL 16). Frontend: Lint, type-check, test, build. Quality gates: Structure/templates/Compose; ML tests; Contract tests and generated docs; Docker images build; **End-to-end (Compose stack + Playwright)** |
| **failure** | **GitGuardian Security Checks** (third-party scanner): 2 "Generic Password" findings (incidents 38441416 and 38441417) in `backend/tests/unit/test_password_policy.py`, commit `df0938f` |

GitGuardian analysis: **false positive.** The flagged strings are synthetic inputs of a password-policy unit test and are deliberately weak passwords that the policy under test must reject; they occur only under `backend/tests/` and authenticate to nothing. Nothing needs revoking or rotating. The check stays red for this PR because it is bound to commit `df0938f` and history is not rewritten. **Owner action required** to clear it: mark the two incidents as false positives (or "test credential") in the GitGuardian dashboard. No scanner configuration was changed by the agent. The PR reports `mergeStateStatus=UNSTABLE` solely because of this check.

### Phase C (part 1): waste reports, photo upload, facilities (this branch)

**Scope boundary, stated plainly.** Done: waste-report intake and review, safe photo upload, facilities. **Not done in this increment:** fleet and collection-task APIs (collection depends on assignment and status workflows that belong with Phase E), a separate "locations/zones" module (none exists in the data model; coordinates live on reports and facilities, and screen 14 still has no owner), and every frontend screen for these modules.

Migration: `0003_waste_report_idempotency` (adds `idempotency_key`, `request_fingerprint`, a both-or-neither CHECK, and `UNIQUE (reporter_id, idempotency_key)`). Verified: upgrade, downgrade to `0002` (columns and constraints verified gone via the catalog), re-upgrade, and `alembic check` reports no drift. `docs/database/data-dictionary.md` regenerated (CI fails if stale; it *was* stale before regeneration).

New dependency: `pillow>=11,<14` (installed 13.0.0), used only to validate and re-encode uploads.

| Check | Command (from the directory shown) | Result |
|---|---|---|
| Backend lint/format/types | `cd backend && ruff check . && ruff format --check . && mypy` | clean (136 source files) |
| Backend tests, real PostgreSQL 16.2 | `cd backend && pytest` | **259 passed** (114 + 145 new: images 17, storage 16, search 7, reports 48, media 25, facilities 32) |
| Schema drift | `cd backend && alembic check` | no new upgrade operations |
| Data dictionary | `python scripts/database/generate_data_dictionary.py --check` | up to date |
| Other suites | `cd ml && pytest`; `pytest tests/contract`; `python scripts/quality/check_structure.py` | 7 passed; 5 passed; ok |
| Mutation checks | break one rule, run the relevant tests | **15/15 caught**: EXIF passthrough, pixel cap, visibility check, idempotency body check, state machine, upload quota, LIKE escaping, storage key allow-list, attaching another user's photo, contact-email visibility, any-of permission check, coordinate-pair check, no-op audit, sensitive value in audit, mutable `code` |

Defects found by testing during this increment (fixed):
1. Migration `0003` downgrade failed: the metadata naming convention is applied again when dropping a CHECK, so the full name produced `ck_waste_reports_ck_waste_reports_...`. Caught by running the downgrade, not by assumption.
2. A partial facility update setting only one coordinate would have been a 500; it is now a 422 (found in code review before the test, then pinned by a test).
3. Mypy found the sort-column map mis-typed and two tests reaching into private re-exports.
4. `ruff format` also reformats Python blocks inside Markdown READMEs (it failed CI-equivalent checks in Phase B); the same trap was avoided here by running the formatter on docs before committing.

Known limitations of this increment (also in `docs/security/security-baseline.md`): no antivirus scan (images are re-encoded instead); unattached uploads are capped per user but not purged automatically; local single-node storage; orphan files are possible if the process dies between writing a file and committing its row; a reverse proxy in front of the API must allow `MAX_UPLOAD_BYTES`; the web app must load photos through `apiRequest` (an `<img src>` cannot send a bearer token); no classification is attached to uploads yet because no model exists.

**CI on PR #6, head `7d4814a` (Phase C part 1; from the check-runs API, not inferred):** 17 check runs, all `success`: Backend lint/type-check; Tests on Python 3.11 and 3.12 with PostgreSQL 16 (push and pull_request); Frontend lint/type-check/test/build; Structure/templates/Compose; ML tests; Contract tests and generated docs; **Docker images build** (confirms the new Pillow dependency installs in the slim image); **End-to-end (Compose stack + Playwright)**. The PR's merge state is `CLEAN`.

**GitGuardian, read carefully:** it posted **no check at all** for the four Phase C commits (neither pass nor fail; the reason is not known), while its **failure on the earlier commits `46bb072` and `2477278` still stands** (the two false positives described above, not yet dismissed in its dashboard). `CLEAN` therefore only means the head commit has no failing check; it is not a scanner approval of the new code. The Phase C tests deliberately contain no password-like literals.

### Phase D: AI/ML waste classification (this branch)

**Scope boundary.** Done: material-category classifier (training, evaluation, serving, API, UI). **Not done:** forecasting and anomaly-detection baselines; object-level labels (the data has none, so `object_label` is always null); any field-data evaluation.

**Commits:** `000d03a` (ML pipeline), `80b97d2` (backend classification), `5909054` (report, model card, registry) and the frontend/e2e commit after it. The registered model was trained from `000d03a` with a clean code tree (recorded in the registry manifest).

**Model:** frozen EfficientNet-EdgeTPU-M TFLite backbone, L2-normalised features, multinomial logistic regression (C = 0.03, picked by a pre-declared one-standard-error rule on grouped CV over the train split only), temperature scaling, review rule. Evidence: `docs/ml/reports/waste-classification-1.0.0.md` (all numbers come from the JSON next to it), model card `docs/ml/model-cards/waste-classification-1.0.0.md`.

| Held-out result (group-aware test split, n = 421, evaluated once) | Value |
|---|---|
| Accuracy | 0.867 (95% CI 0.813–0.912) |
| Macro-F1 | 0.841 (95% CI 0.781–0.887); baseline (hand-crafted features) 0.592 |
| Calibration | ECE 0.031; mean confidence 0.869 vs accuracy 0.867 |
| With the review rule | 73.6% auto-accepted at 96.1% accuracy; 78.6% of errors sent to review |
| Weakest | `trash` F1 0.65 (n = 23); glass is confused with metal; occlusion drops accuracy to 0.66 (over-confident) |
| Latency, bytes to decision, 2 CPU cores (shared sandbox) | p50 about 24 ms, p95 about 26 ms |

**On "high confidence without overfitting or underfitting".** Raw confidence was not maximised: that would be a defect. Accuracy and macro-F1 were maximised on properly held-out data and confidence was *calibrated*; "higher confidence" is an operating point (review threshold 0.81). Over/underfitting evidence: train 0.976 vs grouped-CV 0.843 vs validation 0.821 vs test 0.841 macro-F1 (no selection overfitting; a real generalisation gap that regularisation does not close and the learning curve attributes to data diversity); C = 0.003 underfits, C >= 1 trains to 1.0 without a held-out gain. A leakage control showed a naive random split would have reported 0.893 accuracy; the grouped split reports 0.867.

**Reproducibility:** three full training runs gave identical test metrics. Command: `python -m ml.waste_classification.data.fetch && python -m ml.waste_classification.training.train && python -m ml.waste_classification.evaluation.report`.

Migration `0004_classification_runtime`: richer prediction columns, one-active-model partial unique index, seed of the six material categories. Verified: upgrade, downgrade to `0003` and re-upgrade (test), schema test.

| Check | Command (from the directory shown) | Result |
|---|---|---|
| Backend lint/format/types | `cd backend && ruff check . && ruff format --check . && mypy` | clean (149 source files) |
| Backend tests, real PostgreSQL 16.2 | `cd backend && pytest` | **293 passed** (259 + 34 new: API 17, runtime unit 11, schema 3, CLI 2, real-artifact parity 1 (it RAN locally; it is skipped where the git-ignored artifact is absent)) |
| ML | `cd ml && ruff check . && ruff format --check . && mypy && pytest` | clean; **36 passed** |
| Contract / structure / env | `pytest tests/contract`; `check_structure.py`; `check_env_templates.py` | 5 passed; ok; ok |
| Data dictionary | `generate_data_dictionary.py --check` | up to date |
| Backend mutation checks | break one rule, run classification tests | **7/7 caught**: second review, correction equal to prediction, cross-user read, no idempotent replay, artifact hash unchecked, low-confidence never flagged, unfamiliar image never flagged |
| Frontend | `cd frontend && npm run lint && npm run typecheck && npx vitest run` | clean; **134 passed** (127 + 7 net: 11 classification tests replace 5, +1 raw-body test); UI mutation checks 4/4 caught |
| E2E, real stack with the real model activated | `cd tests/e2e && npx playwright test` | **19 passed, 1 skipped** (the no-model test, which does not apply while a model is active; CI has no model so it runs the other way round). Evidence: `docs/ui/evidence/classification-real-model-result.png` (a real TrashNet photo: Plastic, 67%, flagged for review) |

Defects found and fixed during this phase: the first provenance record named the parent commit because the code was uncommitted (now records `code_tree_clean` and the training was re-run from the commit); the report's latency line printed 8 backbone passes instead of 1; its regularisation wording overstated "worse or no better" (C = 0.1–0.3 are within one SE); mutable class attribute in a test double; `app.cli --help` collapsed its text.

Known limitations: TrashNet only (studio photographs, six classes); no field evaluation; the novelty gate is smoke-tested on 10 non-waste inputs only; timings come from a shared sandbox; the UI category list is a constant that mirrors the model card; `evaluation_metrics` is copied from the artifact at registration; uploaded images are stored when classified (no purge of unattached media); `ai-edge-litert` 2.3.0 has cp311 and cp312 x86_64 wheels (checked on PyPI), but the Docker image itself could not be built here.
