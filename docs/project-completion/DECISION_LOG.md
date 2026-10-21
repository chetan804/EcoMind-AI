# Decision log

Decisions taken during the autonomous build, newest last. Architectural ones have an ADR in `docs/decisions/`. "Owner" items still need the project owner; everything else was decided under the instruction to choose production-grade options without asking.

| # | Date | Decision | Reason | Alternatives rejected | Where |
|---|---|---|---|---|---|
| 1 | 2026-10 | Modular monolith on FastAPI + PostgreSQL; no Redis, broker, Celery, Kubernetes, PostGIS | Locked stack; one deployable unit is enough for the verified requirements | Microservices, queues | ADR-0001 |
| 2 | 2026-10 | Never activate an ML model that is not verified; ship the classifier as a *candidate*, non-default | Honest metrics: TrashNet accuracy 0.867 but 0.454 on RealWaste; 64% of images routed to a person | Marking it production-ready | `docs/ml/model-cards/`, `model_registry/` |
| 3 | 2026-10 | No RealWaste (CC BY-NC-SA) or TrashBox (no licence) data in any released model; TACO unusable (0 of 1,500 images eligible) | Production-level, licence-clean choice | Training on them "for research" and shipping | `docs/ml/dataset-research/` |
| 4 | 2026-10 | Offline map (MapLibre + PMTiles) is the default; Google Maps is opt-in; keys only in env, server key never in the bundle | The owner wants no key and no third-party dependency; Google's terms forbid copying its map | Google-only; scraping tiles | ADR-0002, `docs/maps/` |
| 5 | 2026-10 | Road routing is optional (`ROUTING_PROVIDER=none\|google\|osrm`), nothing stored, never invented | Straight lines are labelled as such; an OSRM server is a documented opt-in deviation | Always-on routing service | ADR-0002 |
| 6 | 2026-10 | Tracking never shows a stationary coordinate as a live vehicle; simulator data is separate and labelled | Honesty contract for operations staff | Showing last-known as live | `docs/api/tracking-api.md` |
| 7 | 2026-10 | Rewards are a hand-over workflow with claim codes; impact is kilograms only, no carbon factor | No sourced coefficient exists; no payment or partner integration is justified | Inventing a CO2 factor | `docs/api/rewards-api.md` |
| 8 | 2026-10 | Supply chain: actions pinned by SHA, hash-locked dependencies, audits in CI | Reproducible builds; base images cannot be digest-pinned from this sandbox (registries unreachable) | Floating tags | `docs/operations/dependency-management.md` |
| 9 | 2026-10 | Registration rate limit is a setting (default 10/IP/hour), relaxed only in the disposable CI stack | CI end-to-end failed with 429s; production default must stay strict | Raising the production limit | `backend/app/core/config.py` |
| 10 | 2026-10-21 | The help assistant is retrieval-only (quotes articles, reads own data, says "I don't know") | No LLM provider/key/data agreement; cannot hallucinate; private; testable offline | Hosted or self-hosted LLM | ADR-0003 |
| 11 | 2026-10-21 | Assistant answers need an anchored match (title or keyword) and 60% query coverage; near misses are only suggested | Body-only coincidences ("time", "name") produced false answers (held-out 2 of 16) | Lower threshold; ranking only | `docs/ml/support-assistant.md` |
| 12 | 2026-10-21 | A chat is shared with staff only when the requester ticks a box; staff reading it is audited; idle chats are purged after 90 days unless attached to a request | Privacy by default | Always attach the chat | `docs/api/support-api.md` |
| 13 | 2026-10-21 (revised same day) | Administrators and managers must use MFA in production; optional elsewhere. Superseded the earlier "optional for all roles" entry | The owner asked for production-grade choices. Built the enrolment-only state properly: the server refuses every non-`/auth` endpoint with `403 mfa_enrollment_required`, checked on every request, plus `409` when a required role tries to switch it off. Blank config can never disable it (`none` is the explicit opt-out) | A flag checked only in the UI (bypassable); a grace period (leaves privileged accounts unprotected); forcing it in local/CI (breaks stacks with no authenticator) | `docs/security/mfa.md`, LIMITATIONS.md |
| 14 | 2026-10-21 | Evaluation sets for the assistant are reported as author-written and, for the held-out one, contaminated | Overstating quality would mislead operators | Presenting the numbers as accuracy | `docs/ml/support-assistant.md` |
| 15 | 2026-10-21 | A collector can read (not change) an incident assigned to them | An assigned collector could not open their own work (audit finding). Visibility is now reporter, assignee or triage staff; re-assigning withdraws it | Giving all collectors read access (leaks other residents' reports); letting assignees change status (a triage permission) | `docs/api/community-incidents-api.md` |
| 16 | 2026-10-21 | Route-plan conflict messages name tasks by title and plans by name; ids stay in `details` | The message showed a raw task id | Showing ids only | `docs/api/route-planning-api.md` |

## Owner decisions on the eight launch questions (2026-10-21)

**Release target:** supervised demonstration or academic submission. **Not approved for a public production launch.** Each entry says what was decided and what, if anything, is still outstanding. "Done" means done in the repository; "Owner action" means something only you (or a person with the needed account) can do.

| # | Decision | Recorded answer | State |
|---|---|---|---|
| 1 | Merge PR #12 | Merge after the latest head passed required CI and the diff was reviewed | **Done.** Head `0b236c5` had every workflow green; the PR was marked ready and merged as `2834cf0`. CI on `main` after the merge has not been checked yet |
| 2 | Google Maps keys | Offline map is the default. Google Maps and Routes are enabled only after restricted keys exist and a live test passes | **Nothing to change in code** (`VITE_MAP_PROVIDER=offline`, `ROUTING_PROVIDER=none` are the defaults). Owner action when wanted: create restricted keys and follow `docs/maps/GOOGLE_MAPS_INTEGRATION.md`. Live Google behaviour is **not verified** |
| 3 | TrashBox | Permission pending; dataset excluded from training, evaluation and distribution | **Owner action:** ask the authors in writing. Until a written permission and licence are on file the exclusion stands (`datasets/manifests/`) |
| 4 | GitGuardian alert | Verify first; dismiss only if confirmed harmless | **Investigated (evidence below); dismissal is still owner-only.** I cannot open the GitGuardian alert, so I could not confirm which line it flagged |
| 5 | Help assistant | Stay retrieval-only | **Done** (ADR-0003). Setting: retrieval-only, no provider, no key |
| 6 | E-mail | Console e-mail for local and supervised demos; verified SMTP before production | **Owner action:** provide SMTP host, port, user, password, sender, TLS mode and the public HTTPS URL as secrets, then send and receive a real test message. Real delivery is **not verified** |
| 7 | Two-step sign-in | Mandatory for administrators; policy configurable for other staff | **Satisfied and stricter by default:** with `ENVIRONMENT=production` and `MFA_REQUIRED_ROLES` blank, administrators **and managers** are required. To require only administrators set `MFA_REQUIRED_ROLES=administrator`; to add collectors and operators set `MFA_REQUIRED_ROLES=administrator,manager,collector,facility_operator`. Enforcement in a real production run and with a real phone is **not verified** |
| 8 | Regional map tiles | Use a regional PMTiles file only after coverage, licence, attribution and offline-use rights are confirmed; routing is configured separately | **Owner action:** choose and approve the source and area (for example Hyderabad). I could not fetch one: the sandbox cannot reach the tile builders. Attribution to the OpenStreetMap contributors is already shown in the map. See `docs/maps/OFFLINE_MAPS.md` |

### GitGuardian investigation (decision 4)

- The alert is "Generic Password" on `backend/tests/api/test_administration.py`.
- That file contains **no password literal in any revision** (checked every commit that touched it). Its only password-like lines are `{"password": STRONG_PASSWORD}` and a check that responses do **not** contain the word "password".
- `STRONG_PASSWORD` is defined in `backend/tests/fixtures/api.py` as `"correct horse battery staple 42"`, a throw-away value used to create users in an ephemeral test database. It protects nothing.
- A scan of the working tree with `detect-secrets` found only: CI service credentials for a disposable Postgres container, placeholder values such as `CHANGE_ME`, symbol alphabets, enum labels, and test fixtures. No `.env`, key or certificate file is tracked.
- A search of the full git history for common live-secret formats (AWS, GitHub, Google API, Slack and OpenAI-style tokens, private-key headers) found nothing.
- **Update 2026-10-21 (exact line found).** GitGuardian's check-run on PR #9 is readable through the GitHub API (`gh api repos/chetan804/EcoMind-AI/check-runs/118817526692`). It names incident **38745160**, detector "Generic Password", commit `402a5852ce2cf68c3a2f52bb8cfb0fe7246fe7cf`, file `backend/tests/api/test_administration.py`, **line 255**. That line (checked with `git show 402a585:backend/tests/api/test_administration.py`) is:

  ```python
  for forbidden in ("secret", "password", "postgresql", "database_url", "storage_path"):
  ```

  inside `test_system_info_exposes_no_secrets`: a list of words the system-info response must **not** contain. It is not a credential and has no value; the detector matched the word "password" next to "postgresql". (The earlier guess that it was `STRONG_PASSWORD` was wrong; that constant is a throw-away test value and was not flagged.) The only scan that flagged anything was this one (PR #9); PRs #10, #11 and #12 scanned clean, and that line no longer exists in the current file.
- **Conclusion:** false positive, now confirmed from the scanner's own output. **Dismissal is still owner-only** (I have no access to the GitGuardian dashboard): open https://dashboard.gitguardian.com/workspace/778224/incidents/38745160, choose "Ignore" > "False positive" (or "used in tests") and note "word list in a test asserting that responses contain no secret words; see DECISION_LOG decision 4".

### Release restriction (unchanged)
Do not declare production readiness until: an approved classifier exists and is evaluated on representative data; real e-mail, maps, routing and GPS are each verified; keyboard and screen-reader testing and load testing are done; and the forced two-step rule is rehearsed in production mode. Mark every item verified, verified only by CI, or not verified.

## Dependency bumps merged after PR #12 (2026-10-21)

Four Dependabot pull requests were merged into `main` at about 14:42 IST, right after PR #12. `main` was then red (Quality gates: the Compose stack and the frontend production image failed; Frontend CI on pull requests failed at `npm ci`). I did not make those merges; this is what I found and did.

| Bump | Finding | Action |
|---|---|---|
| `typescript` 6.0.3 → 7.0.2 in `/frontend` | `npm ci` fails: `typescript-eslint@8.71.2` allows only `typescript >=4.8.4 <6.1.0` | **Reverted** to `^6.0.3` (lock regenerated). `npm ci`, `tsc -b`, `eslint`, the production build and all 365 unit tests pass. Dependabot now ignores TypeScript major bumps until typescript-eslint supports 7 |
| `postgres` 16-alpine → 18-alpine in `compose.yaml` | A major database upgrade is a data migration, not a bump; the 18 images also use a different data directory layout than the `/var/lib/postgresql/data` mount in `compose.yaml`; the backend CI service and every test in this project run on 16. I could not run Docker to test 18 | **Reverted** to `postgres:16-alpine`. Dependabot now ignores PostgreSQL major bumps. Moving to 18 needs its own change: volume path, a tested `pg_upgrade` or dump/restore plan, and CI on 18 |
| `@types/node` 22 → 26 (`/frontend`, `/tests/e2e`) | Type definitions only; the project runs Node 22 in CI and in the images, so the types describe APIs that do not exist at run time | **Kept for now**: `tsc`, eslint, build and tests pass. Worth pinning back to 22 so types match the runtime: recommended, not done |
| `typescript` 7 in `/tests/e2e` | Was already `^7.0.2` before these merges and the browser suite passed with it | Unchanged |
