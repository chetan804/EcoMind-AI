# EcoMind AI — project audit and status report

| | |
|---|---|
| Audit date | 2026-10-21 |
| Code audited | branch `arena/34eb0c5c-ecomind-ai` (draft pull request #12, not merged), starting at commit `7e003df`, plus the audit fixes in commit `111937f` |
| Audited by | an automated coding agent, working only inside a sandbox copy of the repository |
| Method | read the code and documents, ran every automated test and security scan, rebuilt the database from nothing, started the real API and web app, and drove the screens with a headless browser for all five roles |

**How to read this report.** Every claim is marked **Verified** (I ran it and saw the result in this audit), **Proven by CI** (GitHub Actions ran it on an earlier commit; see section 9), or **Not verified** (nobody has shown it works). Nothing is rounded up. If something is missing, it says so.

---

## 1. Verdict in one paragraph

EcoMind AI is a **complete, working web application for a pilot or an academic demonstration**: sign-in with five roles, waste reports, collection tasks, routes, vehicles, facilities, zones, community incidents, a marketplace, rewards, material passports, recovery records, forecasting, anomaly alerts, analytics, an audit log, two-step verification, and a help assistant. The automated tests pass and the security scans are clean. **It is not ready to launch to real users.** Four things stand between "demo" and "live": (1) the AI photo classifier has **no approved model**, so that screen honestly says "No classification model is active"; (2) it has **never been deployed** or tested on a real server, with real e-mail, or with real GPS; (3) the map shows a plain background because **no map tile file is installed**, and Google Maps/Routes have **never been tried with a real key**; (4) the owner decisions listed in section 10 are still open. None of these is a hidden defect. Each is shown in the product and written down.

## 2. Scorecard

| Area | State | Evidence |
|---|---|---|
| Backend API | Complete for the stated scope | 168 operations, 22 modules; **Verified** by 763 passing tests |
| Database | Complete and reversible | 46 tables, migrations 0001–0016; **Verified**: upgrade, no schema drift, full downgrade and upgrade again |
| Role-based access | Complete, tested by probing | 5 roles, 48 permissions; **Verified** against the live API (section 5) |
| Frontend | Complete for the stated scope | 22 module screens, all reachable from the sidebar by the right role; **Verified** by crawl and 365 unit/component tests |
| Security | Strong for a pre-launch app | dependency audits and static analysis clean; **Verified** (section 6) |
| AI photo classifier | **Not usable** | no active model; licence and data limits (section 7) |
| Forecasting | Works, honestly labelled | **Verified** on real public data; beats the naive baseline on two public series |
| Anomaly detection | Works, honestly labelled | **Verified** (scan created 4 alerts on the Austin series) |
| Help assistant | Works, retrieval only | not a language model; limits stated in section 7 |
| Maps and tracking | Works offline without a tile file; live providers unproven | section 8 |
| Deployment | Defined, **never deployed** | Docker setup is proven by CI only |
| Accessibility | Automated checks pass; no human review | axe checks in the browser tests; **Not verified** by keyboard or screen-reader testing |

## 3. Size of the project (counted, not estimated)

| Item | Count |
|---|---|
| Backend Python (application code) | about 22,700 lines |
| Frontend TypeScript/React | about 15,500 lines |
| API operations / paths / data schemas | 168 / 142 / 234 |
| Database tables / foreign keys / check rules / indexes | 46 / 94 / 114 / 205 |
| Backend modules | 22 |
| Roles / permissions | 5 / 48 |
| Backend test files / frontend test files / browser test files | 60 / 37 / 11 |
| Markdown documents tracked in the repository | 147 (plus the three added with this report) |

## 4. Test results from this audit

| Suite | Result | Notes |
|---|---|---|
| Backend (pytest, clean environment like CI) | **763 passed, 1 skipped** in 13 min 44 s | The skip is the test that compares a real trained model; it needs a model file that does not exist. A skip is not a pass. |
| Backend statement coverage | **97%** (10,270 statements, 280 not exercised) | Line coverage only, not branch coverage. |
| Frontend (vitest) | **365 passed** | No frontend coverage figure was measured. |
| Browser end-to-end (Playwright, headless Chromium) | **31 passed, 1 skipped** | Same skipped real-model test. Google Maps cannot load in the sandbox. |
| API contract tests | 37 passed (last run at `7e003df`) | |
| ML pipeline tests | 58 passed | |
| Type checks and style | `mypy`, `tsc -b`, `ruff`, `eslint` clean | |
| Generated documents (data dictionary, ER diagram, route matrix) | up to date | `--check` mode |
| Markdown links | 0 broken across 147 files | |

I also walked through the screens by hand-scripted browser sessions, following the same steps as the manual test guide. These worked: adding a zone, a facility with a zone and coordinates, and a vehicle; creating a collection task; assigning it to a collector with a vehicle; the collector starting it and completing it with a weight (it showed **Completed, 12.5 kg**); creating, ordering and publishing a route plan (it showed **Published**, 23.5 km, "No road route: straight-line fallback"); a citizen reporting an incident and a manager acknowledging it (the citizen was notified); an operator recording a recovery; a manager adding a sorting category and guidance; running a forecast; scanning a series for anomalies; an administrator changing a user's roles with a reason; the audit log; and the system status page. Those walk-throughs were exploratory scripts, not a saved test suite. They exposed no defect in the product. Every failure I hit came from my script's assumptions (a required date or time I had not filled in, an option list that loads a moment late). They are listed in section 11 because the manual test guide warns about them.

## 5. Role-based access: what was checked

I signed in as one account for each role (each holding only that role) and requested every endpoint that takes no parameters. **No request returned a server error.** The access pattern matched the permission table:

- **Administrator only:** audit log, system status details, classification model management.
- **Manager and administrator:** analytics, anomalies, forecasting, user and role administration, rewards ledger/items/redemptions, support queue and statistics.
- **Collector, manager, administrator:** vehicles, route plans, tracking.
- **Citizen (and administrator):** rewards catalogue and personal balance.
- **Everyone signed in:** facilities, zones, marketplace, sorting guide, help articles, notifications, the waste-report list (each role sees what its permissions allow).
- **Not signed in:** every protected route returns 401.

**Sidebar items per role (counted in the crawl):** citizen 13, collector 15, facility operator 15, manager 22, administrator 22. The crawl opened every item as every role and found no error screens. A 404 for `region.pmtiles` on map pages is expected: the page then shows "Base map not installed".

**A real defect found and fixed in this audit:** a collector could not list the incident reports they themselves filed (the permission was missing). Migration 0016 grants it, with a test.

## 6. Security

| Check | Result |
|---|---|
| Python dependency audit (backend and ML) | no known vulnerabilities (**Verified**) |
| npm audit (frontend and browser tests) | none (**Verified**) |
| Static analysis (bandit) | no medium or high findings (**Verified**) |
| Secret scan, `.env` templates, built bundle | no real secrets; the server-only map key is never placed in the browser bundle (**Verified**) |
| Unauthenticated access | 401 on protected routes (**Verified**) |
| Cross-origin request from an untrusted site | rejected (**Verified**) |
| SQL-injection-style login input | handled safely (**Verified**) |
| Error format | a consistent envelope with a request ID; invalid input returns 422 (**Verified**) |
| Response headers | `nosniff`, no-referrer, no-store, request ID (**Verified**) |
| API documentation pages | exposed only in local mode, off in production (**Verified**) |
| Password storage | Argon2id; lockout after 5 failures per e-mail |
| Session | short-lived access token; refresh token in an HttpOnly cookie that needs a CSRF header |
| Two-step verification | optional for everyone; **mandatory for administrators and managers when `ENVIRONMENT=production`** (blocked with a clear message until set up) |
| Web server (nginx) configuration | reviewed by reading; **Not verified** by running nginx (no nginx in the sandbox) |

One open security note: GitGuardian flagged a test password in the git history (`test_administration.py`). It is a throw-away test value, not a real credential, but only the repository owner can dismiss the alert.

## 7. Artificial intelligence: the honest position

**Photo classifier — not usable yet.**
- The product knows six classes: plastic, paper, cardboard, glass, metal, other waste. It cannot recognise organic waste, e-waste or hazardous items.
- A candidate model (`1.0.0`) was trained only on TrashNet (MIT licence). On its held-out test set it scored **accuracy 0.867** (95% interval 0.813–0.912), **macro-F1 0.841**, calibration error 0.031, p95 speed 29.6 ms. Those numbers describe TrashNet photos, which are tidy studio-style images.
- On a different public dataset (RealWaste) the same model scored **accuracy 0.454**. That is a large drop and shows it will not generalise to real-world photos without more data.
- The review rule sends about **64%** of images to a person. This is intentional.
- The model file is **not in the repository** and **no model is active**. So the screen says "No classification model is active". Activating needs an administrator to register and approve a file.
- The licence position stopped further data: RealWaste is non-commercial (CC BY-NC-SA); TrashBox has no licence; the TACO dataset yielded **0 of 1,500** images with a licence we can use. Under the project's production-grade rule none of these may go into a released model.

**Forecasting.** Backtested on real public municipal waste series. Compared with a naive "same as last week" baseline, the error ratio was **0.804 (Austin)** and **0.731 (Ballarat)** in the recorded evaluation (lower is better). In this audit a live Austin run with an 8-week horizon gave **0.66** over 12 test origins. The platform's own series has 0 points until real collections exist. The screen shows the backtest next to every forecast.

**Anomaly detection.** Flags unusual weeks in a series; the scan found 4 on the Austin series. Alerts on public data are labelled "Public reference data".

**Help assistant.** It searches 31 written help articles and reads the signed-in user's own records. It does not generate free-text answers and does not use an outside language model. Measured on questions written by the author: top-answer correct 95% on the 64 development questions, but only **55%** on a held-out set of 40, with **0 wrong answers** (it says "no answer" and offers a support ticket instead). Because the author wrote both sets, treat these as indicative only.

## 8. Maps and tracking

- **Offline map** (MapLibre with an optional PMTiles file): works, but **no tile file is installed**. Pages draw points on a plain background with a clear notice. Installing a regional file is described in `docs/maps/OFFLINE_MAPS.md`.
- **Google Maps and Google Routes**: built, off by default, need keys you hold. **Not verified** with a real key.
- **OSRM road routing**: optional adapter; **Not verified** against a real OSRM server.
- **Route plans** order stops by straight-line distance and say so ("No road route: straight-line fallback"). They are not turn-by-turn navigation.
- **Live vehicle position**: a vehicle appears on the map only if a real position report arrived. A stored coordinate is never shown as a live vehicle. A labelled simulator exists for demonstrations and is kept apart from real data. **Not verified** with a real GPS source.
- Private addresses and reporter identity are not exposed on maps.

## 9. Delivery and CI

- Pull request #12 is a **draft** and is **not merged**. `main` is at `8ebe716` (PR #11).
- CI (GitHub Actions) was green on `7e003df` for every workflow. The audit-fix commit `111937f` was pushed at the end of this audit; its CI result is stated in the hand-over message, not here.
- CI also proves that `docker compose up --build --wait` starts the stack, that the seed and admin commands run, and that the browser tests pass against it. **I could not run Docker in the sandbox**, so the one-command start-up is proven by CI, not by me.
- **Nothing has been deployed.** No production server, domain, TLS certificate, backup job or monitoring exists.

## 10. Decisions only the owner can make

> **Update:** the owner answered all eight on 2026-10-21. The answers, what is done and what still needs an owner action are in `docs/project-completion/DECISION_LOG.md` (section "Owner decisions on the eight launch questions"). The list below is the original question list.

1. Merge draft PR #12.
2. Provide Google Maps/Routes keys (only if Google maps are wanted; the offline map needs none).
3. Ask the TrashBox authors for permission (otherwise it stays unused).
4. Dismiss the GitGuardian alert if satisfied it is a test value.
5. Choose whether the help assistant may use an outside language model and supply a provider and key. Today it is retrieval-only by design.
6. Provide real e-mail (SMTP) settings. Without them, password reset and e-mail verification links appear only in the server log in local mode, and "Forgot password" is hidden in production.
7. Decide whether two-step verification should also be mandatory for collectors and operators.
8. Provide a regional map tile file, or approve building one.

## 11. Findings from this audit

**Fixed in this audit (commit `111937f`)**
1. Collectors could not list their own incident reports. Fixed by migration 0016 and a test.
2. The landing page still said every capability was "planned" and "0 models trained". It now states real facts (5 roles, 6 classes, 3 ML capabilities built, 0 classifiers approved) and says no performance figures are published.
3. Several READMEs and documents were out of date (module counts, "no routes yet", migration head, permission counts, screen evidence). Corrected.
4. The demo seed script failed where only `httpx` was installed. Fixed.
5. A command-line import failed with a confusing error when the reference-data clone was missing. It now gives a clear message, with a test.

**Open issues (none blocks a demo; numbers 1 and 2 are now closed)**
1. ~~A collector who is assigned an incident cannot open it.~~ **Fixed after the audit** (see the update note below).
2. ~~A route-plan conflict message showed an internal ID.~~ **Fixed after the audit.** (Correction: the ID it showed was the *task's* ID, not the other plan's; I described it wrongly in the first version of this report.) The message now names the task by title and the clashing plan by name.
3. The photo classifier, tile file, real maps, real GPS and real e-mail are unproven or absent (sections 7–9).
4. Seeded or newly registered accounts show the "Confirm your email address" banner until the link in the server log is used. This is expected with the console e-mail backend.
5. The first listed task option labels in the route-plan dialog show "title, address" and the checkbox is custom-styled; automated tools must click the label text rather than the box. Not a user problem.
6. There is no frontend coverage measurement and no load or stress test. A light local timing (one user, tiny data, same machine, 30 requests each) gave about 6–8 ms median for list endpoints and 17 ms for the analytics overview. That says nothing about real traffic.

**Update after the audit (2026-10-21, after PR #12 was merged).** An assigned collector can now open (read, not change) the incident assigned to them, with a test; route-plan conflict messages name tasks and plans (tests updated). The owner's decisions on the eight launch questions are recorded in `DECISION_LOG.md`. The PR #12 mentions in sections 9 and 10 are historical: it was merged on 2026-10-21 as `2834cf0`.

## 12. What was not verified (do not assume it works)

- Anything on a real server: deployment, TLS, backups, monitoring, nginx serving `/map-assets/`, container image pinning (registries were unreachable from the sandbox).
- Live Google Maps, Google Routes, OSRM, real OpenStreetMap tiles.
- Real GPS devices, real e-mail delivery.
- The look of the light theme by eye; keyboard-only and screen-reader use.
- The mandatory two-step flow in a browser (it is covered by API and component tests, not a browser test).
- The Flickr and TACO download scripts.
- Docker on the sandbox itself.
- Any behaviour under real user load.

## 13. Recommended next steps, in order

1. Run the manual test (`docs/testing/MANUAL_TEST_GUIDE.md`) and record the results in its scorecard.
2. Decide the owner items in section 10; merge PR #12 once satisfied.
3. Deploy to a staging server with real SMTP, a tile file and `ENVIRONMENT=production`, then repeat the manual test there, including two-step verification.
4. Collect licence-clean, locally photographed waste images with consent, train and evaluate a model, and approve it only if it meets the rules in `docs/ml/evaluation-protocol.md`.
5. Have a person test with a keyboard and a screen reader.

## Related documents
- `docs/PROJECT_GUIDE.md` — everything about the project for a beginner
- `docs/testing/MANUAL_TEST_GUIDE.md` — step-by-step manual test
- `docs/project-completion/LIMITATIONS.md`, `IMPLEMENTATION_STATUS.md`, `DECISION_LOG.md`, `RELEASE_CHECKLIST.md`
