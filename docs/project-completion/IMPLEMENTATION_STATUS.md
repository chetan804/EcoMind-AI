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

## 1. Where the project stands (PR #12 was merged into `main` on 2026-10-21 as `2834cf0`; it was developed on branch `arena/34eb0c5c-ecomind-ai`, started from `main` at `8ebe716`)

`main` is at `8ebe716` (PR #11 merged: offline map, optional OSRM, TACO audit). This branch carries the five production-hardening
steps (Phase J below): supply chain and CI, account recovery, marketplace completion, reward redemption, accessibility audit, plus
three defects found on the way. Alembic head is `0015` (0012 account tokens, 0013 marketplace, 0014 reward catalogue and redemptions, 0015 help assistant and support desk);
48 permissions (new: `rewards:redeem`, `support:ask`, `support:manage`, `knowledge:manage`). Phase K adds the help assistant (retrieval only) and support desk. **Nothing is deployed and the branch is not merged.**

The sections below this one that describe "this branch" in earlier phases (B to I) are history of work that is already on `main`.

**Baseline at the start of this branch (before any change, same sandbox):** backend 524 passed / 1 skipped, vitest 220 passed, `tsc` clean.

Local results at the end of Phase I (the state of `main` at `8ebe716`; Phase J results are listed under that phase):

| Suite | Result |
|---|---|
| Backend pytest (real PostgreSQL 16.2) | 623 passed, 1 skipped (the classification parity test needs the git-ignored model artifact); one more test (transport scheme guard) was added after that run and passes in the re-run of the affected files (58 passed) |
| Backend ruff, ruff format, mypy (as CI runs them, including tests) | clean |
| Frontend vitest | 301 tests passed |
| Playwright e2e (local, real stack, Chromium without extra GL flags) | 22 passed, 1 skipped (the no-model classification test). The first run after the provider change failed the tracking spec (it assumed the Google fallback text); fixed, then the full suite passed. |
| Contract tests (`pytest tests/contract`) | 37 passed (map script 5, TACO scripts 27, others 5) |
| Frontend `tsc -b`, ESLint, production build | clean; no `AIza` key material in the bundle |
| Generated docs (data dictionary, ER diagram, route matrix) `--check` | up to date at `5542389` |
| `scripts/quality/check_structure.py` | passes |

**Not verified (needs credentials or network the sandbox lacks):** rendering with a real Google Maps key, the live Routes API, the CSP with Google
loaded, any real GPS source, the offline map on real OpenStreetMap tiles (only synthetic tiles were rendered), a live OSRM server, the nginx `/map-assets/` location, the TACO source-licence scripts against Flickr. See `docs/maps/GOOGLE_MAPS_INTEGRATION.md` ("Pending live verification").

## 2. Capability matrix

### Backend modules (all 21 have routes, tests and an API document under `docs/api/`)

| Module | Status | Notes |
|---|---|---|
| auth (+ MFA) | **Verified** | Argon2id, refresh cookie, lockout, TOTP MFA with recovery codes (35 tests, 12/12 mutations caught). MFA is optional for every role (not forced). |
| users / roles / permissions | **Verified** | 48 permissions, 5 roles, drift-guard test. |
| administration + audit | **Verified** | Users, roles, deactivate/reactivate, MFA reset, audit log read, system info (14 tests, 9/9 mutations). |
| waste_reports + media | **Verified** | Idempotent create, review workflow, photo upload. |
| classification | **Verified, no model active here** | Real inference service and review flow. The 1.0.0 model is a *candidate* (see §4 Phase D); its artifact is git-ignored and absent in this sandbox, so the screen reports "no model" honestly. |
| collection | **Verified** | Lifecycle with transitions, weights, events, reschedule. |
| facilities, fleet | **Verified** | |
| tracking (vehicle positions) | **Verified with mocks; no live GPS source** | Migration 0011, append-only `vehicle_location_events`, ingestion with validation/authorisation/rate limit, out-of-order and duplicate handling, derived LIVE/DELAYED/STALE/HISTORICAL/SIMULATED status, labelled simulator, retention CLI; 42 API tests plus road-route tests; `docs/api/tracking-api.md`. Real source shipped: browser sharing by the assigned collector (e2e-verified with emulated geolocation). Not a connected GPS fleet. |
| mapping integration (road routing) | **Implemented, mocked, not live-verified** | `backend/app/integrations/mapping`: `ROUTING_PROVIDER=none\|google\|osrm` (default none), Google Routes and OSRM adapters, `GET /route-planning/plans/{id}/road-route`; no key and no OSRM server were available. |
| offline map (default provider) | **Verified with synthetic tiles only** | MapLibre + PMTiles, no key; rendering, clustering, paths, worker, fonts, sprites and CSP checked in real Chromium on invented tiles; needs an owner-prepared real tile file (`docs/maps/OFFLINE_MAPS.md`). |
| route_planning | **Verified** | Deterministic ordering (`route-order 1.0.0`), no stored ETA, no live traffic. Mutation checks 5/5. Optional on-demand road route from the provider (not stored). |
| forecasting, anomaly_detection | **Verified** | `ts-1.0.0`; honest labels for platform vs public reference data. Mutation checks 5/5. |
| sorting_guide | **Verified** | Ships no rules; entries are created by managers. |
| circular_economy (material recovery) | **Verified** | Verification needs a different person than the recorder. |
| material_passports | **Verified** | Chain of custody; integrity check is a consistency check only. |
| rewards | **Verified** | Append-only ledger, staff catalogue, claim-code redemption (hand-over only). |
| support (help assistant, knowledge base, support requests) | **Verified; retrieval only** | Migration 0015, 3 permissions, 38 API tests plus 4 quality tests over two question sets, 11 mutation checks caught; no generative model (ADR-0003); held-out top-1 0.55, contaminated (`docs/ml/support-assistant.md`). |
| notifications | **Verified** | |
| community_incidents | **Verified** | 9 tests; 6 mutations (2 equivalent survivors). |
| analytics | **Verified** | Query-based; `recovery_rate` is null without verified input. |
| marketplace | **Verified** (matching board only) | Listings, requests, accept/decline/withdraw, notifications, audit; migration 0010, 4 permissions, 22 API tests, 5 of 6 mutations caught (the survivor is an unreachable defence-in-depth branch for e-mail visibility), 7 vitest tests, 1 e2e journey. No price, payment, delivery, photos or chat. |
| locations and zones | **Verified** (named zones only) | Zones live in the facilities module (`/api/v1/zones`, migration 0009, 13 tests, 4/4 mutations caught). No boundary geometry (no verified boundary data); the screen maps the zone's facilities. Collection tasks are not linked to zones (future). |

### Frontend screens (see `docs/ui/screen-inventory.md` for routes and permissions)

Every reference screen except 17 and 19 (Smart bins /
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

Frontend: every screen listed in `docs/ui/screen-inventory.md`, over the real API, with shared components, form and dialog helpers, and 212 vitest
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
2. (Done) Marketplace as a matching board; Locations and Zones as named zones without geometry.
3. (Done) Dataset research artifacts. Remaining there: the two owner decisions above; forecasting/anomaly datasets beyond the five ingested
   series were not found.
4. Light-theme contrast audit; password reset and email verification; debounce on users search and audit filters.

### Final round: marketplace, CI repair, release checks (PR #9)

- **Marketplace** built: module `app/modules/marketplace`, migration 0010 (round trip and `alembic check` clean on PostgreSQL 16.2), 4 permissions (catalog and DB agree; drift test passes), API document `docs/api/marketplace-api.md`, screen at `/marketplace`, 22 API tests, 7 vitest tests, one Playwright journey (`tests/e2e/specs/marketplace.spec.ts`), evidence `docs/ui/evidence/screens/marketplace-*.png` (SSIM 0.238; no fidelity claim; cards show category icons, not photos, because no photo upload exists for listings). Mutation checks: 5 of 6 caught; the survivor removes the requester-e-mail visibility condition, which no API path can reach (only owners, managers and the requester ever receive that serializer), so it is kept as defence in depth.
- **Backend CI had been red since `c4a62cb`**: `tests/api/test_security_headers.py` (`/auth/me` case) asked for a database session built from the process environment, which CI does not set (it only sets `TEST_DATABASE_URL`). It passed locally only because the shell exported `DATABASE_URL`. Reproduced in a clean `git worktree` with `env -i`, fixed by overriding `get_db` with a lazy, never-connecting session in the test, then re-ran the whole suite in the stripped environment: 524 passed, 1 skipped (the classification parity test needs the git-ignored model artifact; locally, where the artifact exists, it runs: 525 passed, 0 skipped).
- **GitHub CI on `137e9fa`** (checked with `gh pr checks 9`): Tests (Python 3.11) pass, Tests (Python 3.12) pass, ML tests, Lint and type-check, Lint/type-check/test/build (frontend), Contract tests and generated docs, Structure/templates/Compose, Docker images build and End-to-end (Compose + Playwright) pass. **GitGuardian fails** on one finding: the reviewed false positive in `backend/tests/api/test_administration.py` (a test-only password literal in history).
- Local final counts: backend 525 passed; vitest 220 (27 files); ML 57; Playwright 21 passed, 1 skipped; route matrix 123 operations; Alembic head 0010.

### Phase H: Google Maps and vehicle tracking (this branch, section 27)

Commits on `arena/483a088d-ecomind-ai`: `5542389` (integration), then collector location sharing, the tracking e2e spec, map screenshots and docs.

| Area | What exists | Evidence |
|---|---|---|
| Ingestion and history | `modules/tracking`, migration 0011 (round trip and `alembic check` clean), DB trigger forbidding UPDATE, indexed latest query | `backend/tests/api/test_tracking.py` (42) |
| Road routing | `integrations/mapping/google_routes.py` (header key, field mask, chunking, timeout, quota/denied/network handling) with mocked transport; endpoint always answers 200 with `available` and `reason` | `test_google_routes.py`, `test_road_route.py` (8) |
| Frontend maps | `features/maps` (loader with timeout and `gm_authFailure`, `MapPanel`, `LocationPicker`, fallback), `features/tracking` (fleet map, collection map, sharing, simulator controls) | `frontend/tests/integration/tracking.test.tsx` (20), `tests/unit/{google-loader,maps-geo,tracking}.test.ts` |
| End to end | `tests/e2e/specs/tracking.spec.ts`: collector shares position (emulated geolocation), manager and citizen views, simulated rows labelled and separate, access control | local full suite 22 passed / 1 skipped |
| Screenshots | `docs/ui/evidence/maps/` (five screens, synthetic data, fallback view) | README there |
| Docs | `docs/maps/GOOGLE_MAPS_INTEGRATION.md`, `docs/api/tracking-api.md`, runbook, security review, LIMITATIONS, `SCREEN_TRACEABILITY.md` | |

Defects found and fixed along the way: the e2e Playwright registration budget (10 per IP per hour) is shared by every spec, so the tracking spec registers one account and acts through the seeded administrator and the shared fixtures account; the screenshot script used a non-existent facility type, found by running it.

CI for PR #10 at head `bdd4c15` (`gh pr checks 10`, 2026-10-21): all 10 checks pass (Backend lint/type-check, tests on Python 3.11 and 3.12, frontend, ML, structure/Compose, contract/generated docs, Docker images, end-to-end with the tracking spec, GitGuardian). The first run on `563b18a` failed one frontend test (`operations.test.tsx`, the first test of the file, which waits for a lazily loaded page); the cause is believed to be slow cold imports on the runner (not reproduced locally), and the wait/timeout in `tests/setup.ts` and `vite.config.ts` was raised; this attribution is a diagnosis, not a proven root cause.

### Phase I: offline map, optional OSRM routing, TACO licence audit (branch `arena/cb4875bc-ecomind-ai`)

Production-grade, licence-clean choices (decision: `docs/decisions/ADR-0002-optional-routing-and-map-services.md`).

| Area | What exists | Evidence |
|---|---|---|
| Offline map (default) | `features/maps` provider dispatcher (`VITE_MAP_PROVIDER`), `OfflineMapPanel`/`MapLibreSurface` (MapLibre 6.15, PMTiles 4.5, `@protomaps/basemaps` style with an original palette, supercluster), own-origin web worker, vendored Noto Sans Latin glyphs + sprites (864 KB, OFL/MIT, `frontend/public/map-assets/README.md`), states for no tile file / no WebGL / load error with the list view always available; Google kept as the optional provider | vitest 301 (new: `offline-map` 13, `offline-loader` 4, config, Google tests mocked to the Google provider) |
| Tile preparation and serving | `scripts/maps/prepare_offline_maps.py` (`assets`, `tiles` wrapping `pmtiles extract`), git-ignored `deployment/map-data/`, Vite dev/preview range server (`MAP_DATA_DIR`), nginx `/map-assets/` location, compose mount, env templates | `tests/contract/test_map_scripts.py` (5); the `assets` step was run (9 glyph files copied); the `tiles` step needs the owner's network |
| Browser verification | Chromium + SwiftShader: PMTiles Range requests, worker, glyphs, sprites, markers, clusters, planned/recorded/simulated paths in dev and production builds; CSP with the nginx policy: 0 violations (negative control reports one) | `docs/ui/evidence/maps-offline/` (synthetic tiles, **not a real map**), `tests/e2e/visual/make-synthetic-tiles.py`, `capture-maps.mjs` |
| Defects found by that run | MapLibre 6 looks for its worker next to its own module, so no tile or overlay drew until the worker URL was set through `?worker&url` (jsdom tests could not see this); the tracking e2e spec assumed the Google fallback text | fixed; spec accepts either state |
| Optional OSRM routing | `integrations/mapping/osrm.py`, `factory.py`, settings `ROUTING_PROVIDER`/`OSRM_BASE_URL`/`OSRM_TIMEOUT_SECONDS` validated at startup; off by default; `road_routing_configured` follows the provider | `backend/tests/unit/test_osrm.py` (29), tracking config API test; mocked transport only |
| TACO licence audit | `scripts/ml/taco_licence.py` (audit, owner-run import), `taco_flickr_verify.py` (owner-run Flickr licence check), report `docs/ml/dataset-research/taco-licence-audit.json`: **0 of 1,500 images eligible** (715 no licence, 319 bare "CC", 466 ODbL) | `tests/contract/test_taco_scripts.py` (27); `docs/ml/dataset-research/TACO_LICENCE_AUDIT.md` |
| Dataset policy | RealWaste (NC) and TrashBox (no licence) are not used for any released model; the only model remains the TrashNet candidate (non-default) | `datasets/README.md`, manifests |

Remote CI for this branch: not yet checked at the time of writing (see the verification log of the pull request).

### Phase J: production hardening, steps 1 to 5 (branch `arena/34eb0c5c-ecomind-ai`, PR #12)

| Step | What exists | Evidence (local, this sandbox) |
|---|---|---|
| 1 Supply chain and CI | Actions pinned by commit SHA, runners pinned to `ubuntu-24.04`, hash-locked `backend/requirements.lock`, `backend/requirements-dev.lock`, `ml/requirements-dev.lock` (`scripts/dependencies/lock_backend.sh [--check]`), `scripts/security/run_audits.sh`, workflows `security.yml` and `codeql.yml`, `dependabot.yml`, `docs/operations/dependency-management.md` | `lock_backend.sh --check`, `run_audits.sh` clean; CI green on `455deb4` |
| 2 Account recovery | Password reset and e-mail verification (`/auth/password-reset/*`, `/auth/email-verification/*`, `GET /auth/config`), console/SMTP e-mail backends, migration 0012, CLI `purge-account-tokens` / `mark-email-verified`, three public pages, `docs/operations/account-recovery.md` | backend tests, vitest, e2e `account-recovery.spec.ts`; **no real SMTP delivery tried** |
| 3 Marketplace | Listing expiry (`MARKETPLACE_LISTING_DAYS`), renew, closing outcome, up to four re-encoded photos, CLI `expire-marketplace-listings`, migration 0013, `docs/api/marketplace-api.md` | 26 backend tests plus 5 mutation checks; 14 frontend tests plus 4 mutation checks; e2e with real PNGs |
| 4 Rewards | Staff-entered catalogue, idempotent redemption against a claim code, hand-over, cancel with refund, migration 0014, `docs/api/rewards-api.md`, UI | `test_rewards_catalogue.py` 13 tests plus mutation checks; e2e `rewards-redemption.spec.ts` |
| 5 Accessibility | `scripts/quality/check_contrast.py` (CI step), token fixes (`--color-control-border`, `--color-danger-solid`, `--color-accent-text`, icon text tokens), `ToastProvider` mounted, axe e2e on 20 routes in both themes | one real axe finding (WCAG 2.5.3 on the user-menu trigger) fixed; coverage limits are in `LIMITATIONS.md` |

Defects found by checking, not by being told:

| Defect | Cause and fix |
|---|---|
| Tracking `latest_per_vehicle` used `sqlalchemy.dialects.postgresql.distinct_on`, which exists only in SQLAlchemy 2.1+, while `pyproject.toml` allows `>=2.0,<3` | Rewritten with `row_number()` ordered by `recorded_at desc, received_at desc, id desc` (the `id` tie-break is new; a test fails without it). 43 tracking tests pass on SQLAlchemy 2.1.5 and 2.0.50, and the rest of the backend suite (664 passed, 1 skipped) passes on 2.0.50, so the declared floor is honest |
| `ml/waste_classification/inference/embedder.py` imported `ai_edge_litert` at module level, so importing anything from the package failed without it | Import is lazy and raises `InferenceRuntimeMissingError` naming the fix; new test. 58 ML tests pass in a venv built from `ml/requirements-dev.lock` |
| CI end-to-end job failed on `a97911d` and `b9704d0` | The job's 14 failures were `429 rate_limited` on registration: the suite registers 9 accounts from one address and a Playwright retry registers more, against a hard-coded limit of 10 per address per hour. The limit is now `REGISTRATION_LIMIT_PER_IP_PER_HOUR` (default 10, validated); only the disposable CI stack sets 200. A second, independent race then showed: `tracking.spec.ts` signed in as the shared e2e account without making sure it existed, so it failed when it ran first on a fresh database; it now calls `ensureAccount`. A GitHub annotations reporter was added to the CI Playwright run because the log API in this sandbox cannot be read |

Local results for the branch: backend 706 passed / 1 skipped before the tracking change (the tracking file now has 43 tests); vitest 345; contract 37;
ML 58; e2e 29 passed / 1 skipped on the run before the registration-limit change. **See the PR for the CI result of the final head; it is not recorded here to avoid a stale claim.**

### Phase K: help assistant and support desk (branch `arena/34eb0c5c-ecomind-ai`, PR #12)

Request: "complete the rest of the project: frontend, backend, database, role based auth, ml and an AI chatbot to solve the customer queries". The rest of the areas were already built (see section 2); the missing piece was the chatbot, plus three directive documents.

| Item | What exists | Evidence (local, this sandbox) |
|---|---|---|
| Backend | `backend/app/modules/support/` (retrieval, own-data intents, assistant, knowledge base, tickets), migration 0015 (knowledge articles with a generated search vector, conversations, messages, tickets, replies, 3 permissions), CLI `seed-support-knowledge` / `purge-assistant-conversations`, `ASSISTANT_RETENTION_DAYS` | `test_support.py` 38 tests; `test_cli.py` 5; mutation checks (conversation ownership, feedback target, ticket visibility, reopen on reply, assignee must be staff, purge cutoff, seed keeps edits, transcript consent and audit, procedural-question rule, anchor rule) all failed the suite as they should |
| Quality | 31 starter articles; two author-written question sets in `backend/tests/data/assistant_eval.json`, gated in CI | Development top-1 0.953 (tuned), held-out 0.550 (contaminated), wrong-article 0.031 / 0.000, false answers to out-of-scope questions 0.050 / 0.000; see `docs/ml/support-assistant.md` |
| Frontend | `/assistant` chat (origin label, sources, related articles, feedback, send-to-staff with opt-in chat sharing) and `/support` (my requests; staff queue, usage, article editor); nav entries "Help assistant" and "Support" | vitest 362 passed (17 new); `docs/ui/evidence/screens/assistant-render.png`, `support-queue-render.png`, `support-articles-render.png` |
| End to end | `tests/e2e/specs/support.spec.ts` (two tests), `/assistant` and `/support` added to the axe scan; CI seeds the starter articles | full e2e run on this branch: 31 passed / 1 skipped (`--workers=2`, includes axe in both themes over 22 routes) |
| Documents | `docs/api/support-api.md`, ADR-0003, `docs/ml/support-assistant.md`, runbook section, `LIMITATIONS.md`, `DECISION_LOG.md`, `RELEASE_CHECKLIST.md`, `TRACEABILITY_MATRIX.md`; data dictionary, ER diagram and route matrix regenerated | `--check` of each generator and `check_structure.py` |

Defects found by checking:

| Defect | Cause and fix |
|---|---|
| "How do I redeem my points?" answered with the user's balance | The own-points pattern matched "my points". Added a rule that how-to phrasing with an action verb goes to the help articles; parametrised test |
| Body-only word matches (e.g. "time", "name") produced answers to unrelated questions | Added the anchor rule (title or keyword match required); out-of-scope false answers on the held-out set fell from 2 of 16 to 0 |
| Data-dictionary generator crashed on a generated (`Computed`) column | Handles `Computed` columns |
| Notification "Mark as read" button's accessible name did not contain its visible text (axe `label-content-name-mismatch`, WCAG 2.5.3) | Hidden until the e2e account had a notification; label is now `Mark as read: <title>` and tests updated |
| Security workflow failed on bandit B608 (f-string SQL in the sorting-guide search) | Replaced by one fixed statement with a subquery; `scripts/security/run_audits.sh bandit` now run locally before pushing |
| Backend CI failed on a new CLI test | The test relied on `SECRET_KEY`/`DATABASE_URL` exported in my shell; it now builds its settings explicitly. Reproduced with `env -i` and the full suite re-run that way (750 passed / 1 skipped) |
| Several help articles named screens or buttons wrongly (found by checking each claim against the UI and code) | Corrected: Waste intake records screen, Classification screen title, Guide, Redeem tab, "Send this to the support team", route-plan wording |

Local results at the end of Phase K: backend 750 passed / 1 skipped (full run in a clean environment, `env -i` with only `TEST_DATABASE_URL`); vitest 362; contract 37; e2e 31 passed / 1 skipped; ML unchanged (58, not re-run). **See the PR for the CI result of the final head; it is not recorded here to avoid a stale claim.**

### Phase L: MFA required for privileged roles (branch `arena/34eb0c5c-ecomind-ai`, PR #12)

Role-based authentication had one open gap: two-step verification was optional for everyone, including administrators (previous DECISION_LOG #13). It is now enforced, by policy, in production.

| Item | What exists | Evidence (local, this sandbox) |
|---|---|---|
| Policy | `MFA_REQUIRED_ROLES` (comma-separated roles). Blank/unset: `administrator,manager` in production, nobody elsewhere. `none` opts out. Unknown role names stop startup | `tests/unit/test_config.py` (3 new tests, including "a blank variable does not switch it off") |
| Enforcement | `Principal.mfa_enrollment_required` is computed from the database on every request. `require_permissions`, `require_any_permission` and the new `ActivePrincipal` (used by `GET /classification/model`) answer `403 mfa_enrollment_required`; `/auth/*` stays reachable so the person can enrol. `POST /auth/mfa/disable` is refused (`409 mfa_required_for_role`) for required roles | `tests/api/test_mfa_enforcement.py`, 9 tests: blocked until enrolled; a pending (unconfirmed) factor does not count; a second, unrestricted role does not escape; released immediately after confirmation without a new token; citizens unaffected; not enforced by default outside production. Mutations (removing the check, removing the disable refusal) each failed the suite |
| Client | `mfa_enrollment_required` on `/auth/me` and the sign-in/refresh responses; `RequireAuth` sends such a person to Settings, Security, where a banner explains why; the session user is reloaded when the code is confirmed | `tests/integration/security.test.tsx` 3 new tests (redirect and banner; released after confirmation; others unaffected); the redirect mutation failed the first test |
| Documents | `docs/security/mfa.md` (Required roles section), `docs/api/auth-api.md`, `DECISION_LOG.md` #13 (revised), `LIMITATIONS.md`, `RELEASE_CHECKLIST.md`, `TRACEABILITY_MATRIX.md`, both `.env.example` files, `compose.yaml` | `check_env_templates.py`, `check_structure.py`, route-matrix and data-dictionary `--check` pass |

Not verified: no end-to-end (browser) test of the enforced flow, because the CI stack runs with `ENVIRONMENT=local` (policy off) and a browser test would need a TOTP generator and a privileged account; the API and component tests cover the behaviour. No production deployment exists to observe.

### Phase M: owner follow-ups after PR #17 (branch `arena/94d6b905-ecomind-ai`, started from `main` at `59b337e`)

| Item | What exists | Evidence (local sandbox unless stated) | Not verified |
|---|---|---|---|
| Sign-out defect | The sidebar had no sign-out control, found while writing the keyboard tests. A "Sign out" button now ends the session from the sidebar on every page | 2 component tests; keyboard e2e (navigate and sign out) | – |
| Keyboard e2e | `tests/e2e/specs/keyboard.spec.ts`, 7 tests: skip link, visible focus and no trap, account menu, page-search dialog, phone drawer, keyboard sign-out | 7 passed; full suite 41 passed / 2 skipped (real-model classification; forced MFA enrolment needs the production-mode stack, run separately: `mfa.spec.ts` 4/4) | A person's keyboard review; any screen-reader review |
| MFA browser flow | `specs/mfa.spec.ts` with an RFC 6238 generator: enrol, sign in with a code, recovery code, forced enrolment | 4/4 against a production-mode stack (`ENVIRONMENT=production`, `MFA_REQUIRED_ROLES` blank) | A real authenticator on a phone |
| Load test | `scripts/perf/load_test.py` (read-only, local targets only) and `docs/operations/load-testing.md` | 10 users: 130 req/s, 0% errors, p95 123 ms; 50 users: 122 req/s, 0% errors, p95 639 ms (2 vCPU, one worker, everything on one machine, tiny data); 4 contract tests | Any capacity claim; target hardware; realistic data |
| Offline map from a MapTiler MBTiles file | `scripts/maps/mbtiles_to_pmtiles.py`, OpenMapTiles layout recognised next to Protomaps, style and loader patches, `docs/maps/hyderabad-aoi.geojson` | 8 converter tests, 18 frontend map tests, real-browser render against a **synthetic** tile file | A real MapTiler file (the owner has not downloaded it) |
| Mailpit e2e | `tests/e2e/specs/mail.ts` reads links from the Mailpit inbox API (`E2E_MAILPIT_URL`) or, for local runs, a log file read directly (`E2E_MAIL_LOG_FILE`; the earlier shell-command option was removed as unsafe on 2026-10-21); the CI e2e job runs the stack with `--profile demo-mail`; the mailpit service has a `/mailpit readyz` healthcheck | re-verified 2026-10-21 on the fixed helper: account-recovery spec 4/4 plus helper unit spec 20/20 in log-file mode; full e2e suite 61 passed / 2 skipped through a schema-faithful Mailpit stand-in (SMTP AUTH + REST shapes; not real Mailpit) | **The real Mailpit container: first run is CI** |
| Demo mail | `make demo-mail-up` (Mailpit), `scripts/setup/init_demo_mail.py`, `scripts/demo/verify_smtp_local.py` | 4 SMTP backend tests; the verify script against an independent `aiosmtpd` server (STARTTLS + AUTH succeed; wrong password and untrusted certificate refused) | The Mailpit container (no Docker here); any real provider |
| Demo accounts | `python -m app.cli seed-demo-accounts [--domain] [--reset-passwords]`, password from `DEMO_PASSWORD`; idempotent, audited, refused in production | 5 backend tests (creates six verified working accounts; second run changes nothing; reset changes password and signs out; refused in production; weak password creates nothing; custom domain) | Inside Docker |
| TrashBox research experiment | `ml/waste_classification/research/trashbox_experiment.py`, manifest, `experiments/trashbox-experiment.json`, report section 4b | 3 ML tests; the experiment was run once. Result: helps on TrashBox-like photos, not on RealWaste (0.46–0.48). No model written | Licence (verbal permission only); anything about a released model |
| Dependencies and security | `@types/node` pinned to 22, Dependabot config, `@vitest/coverage-v8`, GitGuardian incident located and documented (dismissal is owner-only) | `npm ci`, lint, typecheck clean | – |

Local totals on this branch: ML 61 passed; backend `tests/integration/test_cli.py` 11 passed; frontend lint and typecheck clean; e2e as above.

### Phase N: engineering follow-ups (branch `arena/e14ca425-ecomind-ai`, PR #20, started from `main` at `217cc25` plus PR #19)

| Item | What exists | Evidence | Not verified |
|---|---|---|---|
| Mailpit in CI | The e2e job and the compose-config job run with `--profile demo-mail`; the account-recovery spec reads the real Mailpit inbox (`E2E_MAILPIT_URL`) and checks sender, recipient, SMTP AUTH user, a link without the token in the query, no token in the notice mail, and no mail for an unknown address | CI on `e131739`: Quality gates (stack start, Mailpit API, Playwright) succeeded; locally 4/4 against a stand-in and 4/4 in log mode | The container on this machine; a real SMTP provider |
| Regional map pipeline | `scripts/maps/build_region_data.py` (`download`, `tiles`, `check-tiles`, `pmtiles`, `crop`, `routing`, `check-routing`, all with `--dry-run`), runbook `docs/maps/HYDERABAD_DATA_RUNBOOK.md`, optional `osrm` compose profile, "© OpenMapTiles" credit when the tile file names it | 53 contract tests (command lines, safety checks, size and checksum handling, with fake runners) and 1 frontend test; compose schema validated in CI with `--profile demo-mail --profile osrm` | Planetiler, OSRM and Docker were never run; image tags, Planetiler's work directory and the Geofabrik `.md5` file are unverified; no real tile file |
| TACO source-licence evidence | `taco_flickr_verify.py` has `fetch` (reads Flickr's live licence table, retries, saves raw answers) and `validate` (offline); shared rules in `taco_evidence.py`; `taco_licence.py audit` ignores tool-written rows that fail validation, counts them, and carries author and photo page into the eligible list | 69 contract tests in `test_taco_scripts.py` and `test_taco_evidence.py` (44 new), mocked transport with synthetic answers; removing the evidence-URL and SHA-256 rules fails 4 tests; audit re-run: still 0 of 1,500 eligible | Every real Flickr call (no key, no access here); Flickr's CC 4.0 licence ids; authenticity of a CSV (validation shows consistency only) |

## Audit (2026-10-21)

A full audit was run and written up in `PROJECT_AUDIT_REPORT.md`; `docs/PROJECT_GUIDE.md` explains the whole project for a beginner and `docs/testing/MANUAL_TEST_GUIDE.md` is the A-to-Z manual test. Results: backend 763 passed / 1 skipped (coverage 97% of statements), frontend 365 passed, browser end-to-end 31 passed / 1 skipped, dependency and static-analysis scans clean. Defects fixed: collectors could not list their own incident reports (migration 0016); the landing page and several READMEs were out of date; the demo seed script needed `httpx2`. Open items are listed in the report (section 11) and `LIMITATIONS.md`. Word copies of the three documents are in `docs/exports/` (Markdown is the source).

## Requirements closure (2026-10-21)

Full evidence, PASS/FAIL/BLOCKED/NOT VERIFIED rows and the verdict are in
[REQUIREMENTS_CLOSURE_REPORT.md](REQUIREMENTS_CLOSURE_REPORT.md). Summary: supervised demo / academic use ready;
public production not ready (no approved classifier, no real e-mail or map data run, no human accessibility
review, no deployment). Local totals: backend 787 passed / 0 skipped, contract 147, ML 61, vitest 386, e2e 61
passed / 2 skipped plus the forced-enrolment spec 4/4 on a production-mode stack; CI on `625241e` green.
