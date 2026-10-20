# EcoMind AI — Implementation Status

Single source of truth for what is built, what is verified, and what is not. Updated as work lands.
Nothing here is claimed without evidence listed in the table or in the "Verification log".

**Status vocabulary**

| Status | Meaning |
|---|---|
| Verified | Implemented and covered by automated tests that were run and passed |
| Partial | Some of the behaviour exists; gaps are listed |
| Planned | Visible in the product as "Soon" or documented only; nothing is faked |
| Missing | Not started |
| Blocked | Cannot be completed in this environment; reason given |

## 1. Where the project stands (branch `arena/39c812ff-ecomind-ai`, PR #9 against `main`)

`main` is at `4474bfb` (PR #7). PR #9 adds community incidents, analytics, administration, MFA and every
remaining frontend screen. Alembic head is `0008`.

Latest local results on this branch (run in this sandbox; CI results are listed in the verification log):

| Suite | Result |
|---|---|
| Backend pytest (real PostgreSQL 16.2) | 477 passed, 1 skipped (2 further tests for the review-queue image endpoint are green in CI; the skip is the classification parity test, which needs the git-ignored model artifact that is not in this sandbox) |
| Backend ruff, ruff format, mypy (as CI runs them, including tests) | clean |
| Frontend vitest | 23 files, 207 tests passed |
| Frontend `tsc -b`, ESLint, production build | clean |
| `scripts/quality/check_structure.py` | passes |

## 2. Capability matrix

### Backend modules (all 19 have routes, tests and an API document under `docs/api/`)

| Module | Status | Notes |
|---|---|---|
| auth (+ MFA) | **Verified** | Argon2id, refresh cookie, lockout, TOTP MFA with recovery codes (35 tests, 12/12 mutations caught). MFA is optional for every role (not forced). |
| users / roles / permissions | **Verified** | 36 permissions, 5 roles, drift-guard test. |
| administration + audit | **Verified** | Users, roles, deactivate/reactivate, MFA reset, audit log read, system info (14 tests, 9/9 mutations). |
| waste_reports + media | **Verified** | Idempotent create, review workflow, photo upload. |
| classification | **Verified, no model active here** | Real inference service and review flow. The 1.0.0 model is a *candidate* (see §4 Phase D); its artifact is git-ignored and absent in this sandbox, so the screen reports "no model" honestly. |
| collection | **Verified** | Lifecycle with transitions, weights, events, reschedule. |
| facilities, fleet | **Verified** | |
| route_planning | **Verified** | Deterministic ordering (`route-order 1.0.0`), no ETA, no live traffic. Mutation checks 5/5. |
| forecasting, anomaly_detection | **Verified** | `ts-1.0.0`; honest labels for platform vs public reference data. Mutation checks 5/5. |
| sorting_guide | **Verified** | Ships no rules; entries are created by managers. |
| circular_economy (material recovery) | **Verified** | Verification needs a different person than the recorder. |
| material_passports | **Verified** | Chain of custody; integrity check is a consistency check only. |
| rewards | **Verified** | Append-only ledger, no redemption. |
| notifications | **Verified** | |
| community_incidents | **Verified** | 9 tests; 6 mutations (2 equivalent survivors). |
| analytics | **Verified** | Query-based; `recovery_rate` is null without verified input. |
| circular surplus marketplace | **Planned** | No backend; the nav item says "Soon". |
| locations and zones | **Missing** | No module; facilities is the closest concept. |

### Frontend screens (see `docs/ui/screen-inventory.md` for routes and permissions)

Every reference screen except 08 (Marketplace, planned), 14 (Locations and Zones, not built), 17 and 19 (Smart bins /
telemetry, excluded by product decision) has a working React screen over the real API. Real-browser renders, side-by-sides
and diffs for 05–22 are in `docs/ui/evidence/screens/`; their similarity numbers are low and are **not** a fidelity claim
(`docs/ui/evidence/README.md`). A stored light theme exists because those references are light screens; its contrast is not
audited screen by screen. The prediction review queue (`/classify/review`) exists, with a reviewer-only photo endpoint.

### ML

| Area | Status |
|---|---|
| Image preprocessing, classification training/eval/inference | Verified (ML tests); model 1.0.0 is a candidate, not released |
| Forecasting benchmark (Austin, Ballarat and others) | Verified; `docs/ml/dataset-research/experiments/time-series-results.json` |
| Dataset research (catalogue, manifest, selection report, ingestion, rejected list) | **Rebuilt and verified** 2026-10-20: `docs/ml/dataset-research/`. RealWaste ingested (4,752 images, checksummed, group-aware); cross-dataset evaluation and a bounded multi-dataset experiment (experiment-only: RealWaste is non-commercial) |
| Model 1.0.0 on real facility photos (RealWaste, never seen) | **0.454 accuracy (95% CI 0.437–0.472), ECE 0.263**; the review rule sends 64% to a person and 96% of unsupported-class images. Stated in the model card |

## 3. Blockers, losses and environment limits

- **Lost research tooling (rebuilt).** A sandbox reset once removed the uncommitted research code and logs. It was rewritten and committed
  (`ml/waste_classification/research/`, `ml/tests/test_dataset_research.py`); no number from the lost logs is quoted. Every figure in
  `docs/ml/dataset-research/` was recomputed from re-fetched, checksummed data, and the experiment was run twice with identical output.
- **What the research concluded** (`DATASET_SELECTION_REPORT.md`): the TrashNet model does not transfer to real photos (0.45); training on
  real photos would lift it to about 0.79 on the shared classes at some cost on studio images, but the only reachable labelled real-world set
  is CC BY-NC-SA 4.0, so no such model is released or activated. No taxonomy class was added (organic/textile: RealWaste only; e-waste/medical:
  TrashBox, which has no licence). **Owner decisions needed:** (A) is the deployment non-commercial research so a clearly-labelled research
  model trained on RealWaste is acceptable? (B) permission from the TrashBox authors, or an owner-run TACO download with a licence audit.
- **Unreachable sources** (ZeroWaste, Kaggle sets, RecyBat24, TACO images) are listed as unverified in the catalogue; nothing about them is asserted.
- **Network allow-list:** github.com, codeload.github.com, api.github.com, registry.npmjs.org, pypi.org, files.pythonhosted.org. Hugging Face,
  PyTorch hosts and Google Cloud Storage are unreachable.
- Docker is not available in the sandbox; Compose is validated by schema locally and by CI.
- No deployment target or credentials: nothing is deployed.
- **GitGuardian** reports failures on PR #6 (two findings) and PR #9 (one finding); all are inspected false positives (see the log). History
  is not rewritten; the owner must mark them in the GitGuardian dashboard.

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
- At the end of this phase there was no MFA (added in Phase G), password reset, email verification, or social sign-in (buttons stay disabled, labelled unavailable). Password reset and email verification still do not exist.
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

**Commits:** `000d03a` (ML pipeline), `80b97d2` (backend classification), `5909054` (report, model card, registry), `72a80ad` (frontend + e2e), `12c93a5` (fix: tracks the data-loader package that `.gitignore` was hiding). The registered model was trained from `12c93a5` with a clean code tree, recorded in the registry manifest; the check counts ignored `.py` files as not clean.

**Model:** frozen EfficientNet-EdgeTPU-M TFLite backbone, L2-normalised features, multinomial logistic regression (C = 0.03, picked by a pre-declared one-standard-error rule on grouped CV over the train split only), temperature scaling, review rule. Evidence: `docs/ml/reports/waste-classification-1.0.0.md` (all numbers come from the JSON next to it), model card `docs/ml/model-cards/waste-classification-1.0.0.md`.

| Held-out result (group-aware test split, n = 421, evaluated once) | Value |
|---|---|
| Accuracy | 0.867 (95% CI 0.813–0.912) |
| Macro-F1 | 0.841 (95% CI 0.781–0.887); baseline (hand-crafted features) 0.592 |
| Calibration | ECE 0.031; mean confidence 0.869 vs accuracy 0.867 |
| With the review rule | 73.6% auto-accepted at 96.1% accuracy; 78.6% of errors sent to review |
| Weakest | `trash` F1 0.65 (n = 23); glass is confused with metal; occlusion drops accuracy to 0.66 (over-confident) |
| Latency, bytes to decision, 2 CPU cores (shared sandbox) | p50 about 23 ms, p95 about 30 ms |

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

Defects found and fixed during this phase: **the `.gitignore` rule `ml/*/data/*` hid the source package `ml/waste_classification/data/`, so `72a80ad` was pushed without `fetch.py`/`trashnet.py`; CI caught it (ML tests and the structure check failed on that commit), and ruff had silently skipped the files locally because it honours `.gitignore`. Fixed in `12c93a5`, the files were then linted and type-checked for the first time (3 ruff and 2 mypy findings fixed), and the model was retrained from the corrected commit (identical metrics, fourth identical run);** a second CI-only failure followed: the ML mypy step failed on Python 3.12 because numpy 2.5.4 (installable only on Python >= 3.12; 3.11 gets 2.4.6) has stricter stubs that reject a bare `ndarray.max()`; it could not be reproduced locally on 3.11, so the CI job's single bundled step was split into separate named steps and a temporary diagnostic surfaced the mypy output; fixed with `np.max` in `d9b204d` (semantics unchanged, so the model was not retrained; its registry `git_commit` `12c93a5` remains the commit it was trained from); the first provenance record named the parent commit because the code was uncommitted (now records `code_tree_clean` and the training was re-run from the commit); the report's latency line printed 8 backbone passes instead of 1; its regularisation wording overstated "worse or no better" (C = 0.1–0.3 are within one SE); mutable class attribute in a test double; `app.cli --help` collapsed its text.

Known limitations: TrashNet only (studio photographs, six classes); no field evaluation; the novelty gate is smoke-tested on 10 non-waste inputs only; timings come from a shared sandbox; the UI category list is a constant that mirrors the model card; `evaluation_metrics` is copied from the artifact at registration; uploaded images are stored when classified (no purge of unattached media); `ai-edge-litert` 2.3.0 has cp311 and cp312 x86_64 wheels (checked on PyPI), but the Docker image itself could not be built here.

**CI on PR #6, head `d9b204d` (Phase D; from the check-runs API):** all project jobs `success`: Backend lint/type-check; Tests on Python 3.11 and 3.12 with PostgreSQL 16; Frontend lint/type/test/build; ML tests (Python 3.12); Structure, templates and Compose; Contract tests and generated docs; **Docker images build** (backend image with numpy and `ai-edge-litert` on python:3.12-slim, and the frontend image); **End-to-end (Compose stack + Playwright)**. These Docker and Compose results are the first real verification of the container path, which could not be run in the sandbox. In CI no model is active, so the classification e2e runs its "no active model" test and skips the real-model test (which was run locally with the trained model: see above). GitGuardian: see its own check.

### Phases E–G: operations modules, administration, MFA, full frontend (PRs #7, #8, #9)

Backend (see each `docs/api/*-api.md`): fleet, collection, forecasting, anomaly detection, route planning, sorting guide, material recovery,
passports, rewards, notifications (PRs #7/#8, merged or green earlier); community incidents, analytics, administration and MFA with migration
`0008` (PR #9). Each module's tests include at least one round of deliberate mutation (break one rule, confirm a test fails); the counts are in §2.

Frontend: every screen listed in `docs/ui/screen-inventory.md`, over the real API, with shared components, form and dialog helpers, and 207 vitest
tests. Visual comparison for screens 05–22: `docs/ui/evidence/screens/` (demonstration data only, seeded by `scripts/demo/seed_demo.py`; real
public reference series imported from the pinned `msw-src` commit).

Defects found and fixed while capturing the screens (not hidden): chart date labels overlapped on 60-point series; a long table row header made a
page 2,800 px wide; "1 verified records" was not singular; the app had no light theme although references 05–22 are light.

**CI on PR #9, head `998aa4a` (`gh pr checks 9`, 2026-10-20):** all 9 project jobs pass, including End-to-end (with the core-workflow spec) and Tests on Python 3.11 and 3.12; GitGuardian fails (false positive below). Earlier, head `4e9e2fb`: all 9 project jobs `success` (contract/docs, Docker, end-to-end, both lint jobs,
frontend, ML, structure, Python 3.11, Python 3.12). The later commits on this branch (`e4b0b98`, `3738208` and what follows) have **not** yet
been checked; re-run `gh pr checks 9` before relying on them.

**GitGuardian on PR #9:** 1 "Generic Password" finding, commit `402a585`, `backend/tests/api/test_administration.py` line 255. Inspected individually:
it is a tuple of words (`"secret"`, `"password"`, `"postgresql"`, ...) in `test_system_info_exposes_no_secrets`, which asserts the system-info
endpoint contains none of them. It is not a credential; nothing to rotate. It stays red because history is not rewritten. Owner action: mark the
incident as a false positive in the GitGuardian dashboard.

**Not done yet (next actions):**
1. Extend the Playwright core-workflow spec beyond collection (recovery, passport). It currently covers report → verified task → assignment (collector and vehicle) → collected weight → reward → analytics, passes locally (21 specs: 20 passed, 1 skipped) and needs `E2E_ADMIN_*` (CI creates the administrator); its CI result is not yet confirmed.
2. Locations and Zones (needs a backend decision); Marketplace (needs a backend).
3. (Done) Dataset research artifacts. Remaining there: the two owner decisions above; forecasting/anomaly datasets beyond the five ingested
   series were not found.
4. Light-theme contrast audit; password reset and email verification; debounce on users search and audit filters.
