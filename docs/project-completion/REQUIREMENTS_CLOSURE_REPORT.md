# Requirements closure and release-readiness report

| | |
|---|---|
| Date | 2026-10-21 |
| Starting point | `main` at `95e1036` (PR #20 merged, CodeQL autofix PRs #21 and #22) |
| Changes of this task | PR #23, merged by the owner as `625241e` (`7fadec4` e2e mail helper; `05e514c` migration 0017, bbox filter, requirements rewrite), then the documentation commits on branch `arena/174cfaa2-ecomind-ai` that follow it |
| Done by | an automated coding agent, in a sandbox without Docker, without Planetiler/OSRM, and with only GitHub, PyPI and npm reachable |

**How to read this.** Each row is **PASS** (a command was run and its result is quoted), **PASS (CI only)** (the
GitHub Actions run succeeded; I could not run it here), **FAIL**, **BLOCKED** (needs something only the owner can
supply) or **NOT VERIFIED** (nobody has shown it either way). A skipped test is never counted as a pass.

## 1. Verdict

* **Academic submission / supervised demonstration: ready.** The application runs end to end, every automated
  gate is green, and the limits are documented ([LIMITATIONS.md](LIMITATIONS.md)).
* **Staging: not verified.** No deployment exists, so nothing about a real host, HTTPS, backups or monitoring has
  been exercised.
* **Public production: NOT ready.** The reasons are in section 5; none of them can be closed by changing code.
  The classifier is not approved and none is active, real e-mail and real map data have never been run, and no
  person has done a keyboard/screen-reader review.

## 2. Code changes made in this task

| Change | Path | Evidence |
|---|---|---|
| **P0 security fix.** The e2e mail helper no longer runs a shell command taken from an environment variable. It reads the Mailpit REST API (`E2E_MAILPIT_URL`) or a log file (`E2E_MAIL_LOG_FILE`) directly. `child_process` is not imported anywhere in `tests/e2e` | `tests/e2e/specs/mail.ts`, `mail.unit.spec.ts`, `visual/capture-auth.mjs`, `tests/contract/test_e2e_no_shell_execution.py` | 20 helper tests (mutation-checked), the guard test, both modes (section 3) |
| Audit log and collection status history are append-only in the database, not only by convention (only `actor_id` → NULL, from the user-delete FK, is allowed) | `backend/migrations/versions/0017_*.py`, `tests/integration/test_append_only_records.py` | migration round trip, `alembic check`, tests, trigger refusing `DELETE` on a restored copy |
| `FR-REP-2`: waste reports filter by bounding box (API only; the list screen does not expose it) | `backend/app/modules/waste_reports/`, 9 tests | `tests/api/test_waste_reports*.py` |
| `docs/requirements/functional-requirements.md` rewritten against the code and tests; stale "Not started" statuses removed | `docs/requirements/` | row-by-row evidence column |
| Stale claims reconciled (scope, roadmap, design-system status, screen inventory, audit report note, traceability matrix, limits) | `docs/` | diff |
| New: blank manual keyboard and screen-reader test form | `docs/testing/ACCESSIBILITY_MANUAL_CHECKLIST.md` | not executed by anyone |
| Backup/restore drill repeated at migration 0017 | `docs/operations/backup-and-rollback.md` | section 3 |
| Decisions 20–22 | `DECISION_LOG.md` | |

## 3. Commands run and their results

All local runs: Python 3.11.2, Node 22.22.3, PostgreSQL 16.2, headless Chromium, 2 CPUs.

| Check | Command | Result |
|---|---|---|
| Backend tests, CI-like environment | `env -i … TEST_DATABASE_URL=… python -m pytest -q -p no:cacheprovider` in `backend/` | **787 passed, 0 skipped** in 11 min 20 s on the merged tree (`2d230ff` plus docs). The earlier run on `7fadec4` had 773 passed / 1 skipped; the skipped test (model-artifact parity) ran this time because the reproduction above had rebuilt the git-ignored candidate artifact. The artifact is not shipped and not active |
| Backend lint, format, types | `ruff check .`, `ruff format --check .`, `mypy` | clean (run on the backend changes, see the CI row) |
| Migrations | `alembic upgrade head`, `alembic check`, `downgrade 0016` then `upgrade head` on a scratch DB and on a restored backup | clean; head `0017` |
| Contract and structure tests | `pytest tests/contract` | 147 passed |
| Frontend | `npm ci`, `npx tsc -b`, `npm run lint`, `npm test`, `npm run build` | all clean; vitest 386 passed (39 files). No frontend source changed after this run |
| ML unit tests | `python -m pytest ml/tests` | 61 passed |
| **ML reproduction** | `python -m ml.waste_classification.data.fetch`, `…training.train`, `…evaluation.report` | datasets fetched and hash-verified; retraining gave accuracy 0.8670, macro-F1 0.8409, ECE 0.0310 on the TrashNet test split, the same as the registered 1.0.0 values. `head.npz` and `novelty_reference.npy` hashes were identical to the registry; only timestamps and latency differ. Rewritten tracked files were reverted |
| E2E, log-file mail mode | `cd tests/e2e && npx playwright test specs/account-recovery.spec.ts specs/mail.unit.spec.ts --workers=1` with `E2E_MAIL_LOG_FILE` | 24 passed (4 + 20) |
| E2E, full suite, Mailpit-shaped mode | full `npx playwright test --workers=1` with `E2E_MAILPIT_URL` pointing at a local stand-in (SMTP with mandatory AUTH plus the Mailpit REST shapes; **not real Mailpit**) | **61 passed, 2 skipped** (63 tests) |
| The 2 skips | `classification.spec.ts:40` needs a real model (none is shipped); `mfa.spec.ts:130` needs a production-mode stack | counted as **not passed** in that run |
| Forced two-step enrolment | second API with `ENVIRONMENT=production`, `REFRESH_COOKIE_SECURE=true`, fixed CORS origin, plus a second Vite; fresh admin; `E2E_ENFORCED_URL/EMAIL/PASSWORD` set; `specs/mfa.spec.ts` | 4 passed, including the forced-enrolment test that is skipped otherwise. The production-mode API also started, which proves startup validation accepts that configuration |
| Smoke test | `python3 tests/smoke/smoke.py --api … --web …` against both stacks | `smoke ok` ×2 |
| Dependency audits and static analysis | `scripts/security/run_audits.sh all` (pip-audit ×2, npm audit ×2, bandit) | no findings (run on `7fadec4`; the later backend change is covered by CI bandit) |
| Secret scan | `detect-secrets scan` over all tracked files (127 candidates) | every candidate inspected by pattern: placeholders (`CHANGE_ME`, `USER:PASS`), CI-only throw-away values, test fixtures, `ABCDEFGH…` alphabets, content hashes in manifests, and the documented example passwords. No real credential found. This is a heuristic scan of the current tree, **not** a history scan |
| Backup and restore drill | `pg_dump --format=custom`, `pg_restore --no-owner --exit-on-error` into a new DB | 47 tables, 809 rows, `alembic_version`, 5 triggers identical; the trigger refused `DELETE FROM audit_logs` on the copy |
| Map pipeline | `build_region_data.py download --dry-run`; `check-tiles` | dry run works; the real download is unreachable from the sandbox; `check-tiles` reports that `region.pmtiles` does not exist (**BLOCKED**) |
| Workflow files | read for `github.event.*` expressions in `run:` steps and for permissions | none found; `contents: read` |

### CI on GitHub (service-reported)

| Commit | Result |
|---|---|
| `05e514c` (pull request) | Backend CI, Quality gates, Security, CodeQL: success |
| `625241e` (merge of PR #23 into `main`) | Backend CI, Quality gates, Security, CodeQL: success. Quality gates includes the end-to-end job against the **real Mailpit container**, whose Playwright step succeeded, and the Docker image build |
| `95e1036` (`main` before) | Security, Frontend CI, CodeQL, Quality gates: success |

I could not read CI logs, so the skip count of the CI Playwright run is not known. The code-scanning alert list
is not readable with the available token (HTTP 403), so open CodeQL alerts were **not verified** beyond the
workflow succeeding.

## 4. Requirement status

Source of truth: [functional-requirements.md](../requirements/functional-requirements.md), with the matrix in
[TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md).

| Area | Status | Evidence or limit |
|---|---|---|
| Authentication, sessions, RBAC (48 permissions, 5 roles), deny-by-default routing | PASS | `test_route_inventory.py`, auth tests, live probe of every role in the audit |
| Two-step verification, forced for administrators and managers in production | PASS | unit tests plus the browser run above. Collectors/operators are not forced (owner decision) |
| Account recovery, e-mail verification | PASS in code and with a stand-in; PASS (CI only) with real Mailpit; **BLOCKED with a real SMTP provider** | needs owner credentials |
| Waste reports, media validation, area filter | PASS | tests; the bbox filter is not in the UI |
| Collection, fleet, facilities, zones, recovery, passports, rewards, marketplace, incidents, notifications | PASS | API tests, e2e journeys |
| Audit trail and append-only records | PASS | DB triggers on 5 tables; TRUNCATE is not covered |
| Dashboards, analytics | PASS | numbers equal stored records |
| Forecasting | PASS, labelled | beats the naive baseline on 2 of 4 public series |
| Anomaly detection | PASS for injected spikes only | **NOT VERIFIED on real data** |
| Route planning | PASS as straight-line order; road routing optional (OSRM adapter) and verified only against mocks | shown as a fallback, never as navigation |
| Support assistant | PASS | retrieval-only over 31 articles; no LLM |
| **Waste classification** | **PARTIAL, not release-approved** | material category only; `object_label` is null; no model is active and the API answers 503 `no_active_model`. Candidate 1.0.0: TrashNet accuracy 0.867; on RealWaste 0.454 (95% CI 0.44–0.47), 64% sent to review. Training data licence is research-only for RealWaste; TrashBox has verbal permission only |
| Object recognition ("what is this item") | **FAIL / not delivered** | no model identifies objects; the UI and docs do not claim it |
| Maps, offline MapLibre/PMTiles | PASS for the code (browser-verified in an earlier phase with a synthetic tile set, not a real map); **BLOCKED for real Hyderabad tiles** | `docs/maps/hyderabad-aoi.geojson` is an area outline, not tile data |
| Google Maps provider | **BLOCKED** | needs owner keys; never loads in the sandbox |
| Live vehicle tracking | PASS with a simulator and emulated geolocation, labelled | **NOT VERIFIED with a real device** |
| Smart bins and telemetry | Not in navigation, by decision | internal adapter only |
| UI against the 22 reference screens | Implemented; **NOT VERIFIED as matching** | earlier similarity measurements were low (SSIM 0.24–0.57 against small composite references). I did not repeat the comparison in this task. Needs a person's design sign-off |
| Automated accessibility | PASS | axe over 22 routes in both themes plus 7 keyboard tests |
| Keyboard and screen-reader review by a person | **NOT VERIFIED** | form: `docs/testing/ACCESSIBILITY_MANUAL_CHECKLIST.md` |
| Load | Sandbox figures only: 10 users 130 req/s, p95 123 ms, 0% errors; 50 users 122 req/s, p95 639 ms | **NOT VERIFIED** on target hardware; not a capacity claim |
| Docker image build, Compose stack | PASS (CI only) | no Docker locally |
| Deployment, HTTPS, monitoring, backups in production | **NOT VERIFIED** | no environment exists |

## 5. Owner-only actions that gate a wider release

1. Decide the classifier: supply licence-clean, representative training data (or written TrashBox permission and a
   licence), evaluate it, and approve activation. Until then leave it inactive.
2. Provide real SMTP values through secrets (never in chat) and send one real test message.
3. Obtain Hyderabad vector tiles under their licence (MapTiler or Geofabrik with Planetiler), convert with
   `scripts/maps/mbtiles_to_pmtiles.py`, put `region.pmtiles` in `deployment/map-data/`, and test the map in a
   browser. Optionally run OSRM.
4. Provide Google browser/server keys only if that provider is wanted.
5. Have people complete the accessibility form, and sign off the UI against the references.
6. Authorize a staging deployment (host, domain, HTTPS, backups, monitoring); then run the smoke test, a load test
   on that hardware and the release checklist.
7. Dismiss GitGuardian incident 38745160 (a false positive on a test fixture) if you agree after reading it.
8. Decide whether collectors and facility operators must use two-step verification before production.

## 6. Release checklist

[RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) lists every gate with its owner. Items tested here are only the
code-side ones in section 3; the configuration, data, ML and deployed-stack sections remain unticked on purpose.
