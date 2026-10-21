# Release checklist

Tick each item with evidence (a command output, a CI run URL, a screenshot path). Items marked **owner** cannot be done by the build. Nothing in this repository has been deployed; this list is what must be true before the first deployment.

## 1. Code and CI
- [ ] Release branch is up to date with `main`; no unresolved review comments.
- [ ] CI green on the exact commit: backend-ci, frontend-ci, quality-gates (includes end-to-end and contrast audit), security, codeql. (`gh api "repos/chetan804/EcoMind-AI/actions/runs?head_sha=$(git rev-parse HEAD)"`)
- [ ] Locks are current: `scripts/dependencies/lock_backend.sh --check`; `scripts/security/run_audits.sh` has no unaccepted finding.
- [ ] Generated documents are current: `generate_data_dictionary.py --check`, `generate_er_diagram.py --check`, `generate_route_matrix.py --check`, `scripts/quality/check_structure.py`.
- [ ] Security scanner findings are each investigated; GitGuardian dismissals are made by the owner with a reason. **owner**

## 2. Database
- [ ] `alembic upgrade head` on a copy of production data; `alembic check` reports no operations.
- [ ] Backup taken and restore rehearsed (`docs/operations/backup-and-rollback.md`); rollback plan names the migration to downgrade to and which migrations are not reversible without data loss.
- [ ] Current head: `0016` (collectors read their own incidents). Applies after `0015`.

## 3. Configuration (no secrets in the repository)
- [ ] `SECRET_KEY` generated, `ENVIRONMENT=production`, `DATABASE_URL` set, startup validation passes.
- [ ] `EMAIL_BACKEND=smtp` with a real server **and a test message delivered**; `APP_BASE_URL` is the public HTTPS origin. **owner** (SMTP account)
- [ ] `REGISTRATION_LIMIT_PER_IP_PER_HOUR` left at its default; `ASSISTANT_RETENTION_DAYS`, `MARKETPLACE_LISTING_DAYS`, `REWARD_POINTS_PER_KG` reviewed.
- [ ] Map: tiles file installed under `MAP_DATA_DIR` (or `VITE_MAP_PROVIDER=google` with a restricted browser key); `ROUTING_PROVIDER` chosen. Server-side Google key is never in a `VITE_` variable.
- [ ] CORS, cookie, HTTPS and security headers verified on the real host (`docs/security/security-baseline.md`).

## 4. Data and accounts
- [ ] First administrator created with `python -m app.cli create-admin`; the password is not reused and not logged.
- [ ] `python -m app.cli seed-support-knowledge` run; the help articles reviewed for this organisation's policies.
- [ ] Demo data (`scripts/demo/seed_demo.py`, local-only by design) has not been run against this database.
- [ ] Scheduled jobs installed: `purge-account-tokens`, `expire-marketplace-listings`, `purge-assistant-conversations`.
- [ ] `MFA_REQUIRED_ROLES` reviewed (default: administrators and managers in production). Existing privileged accounts are held to Settings, Security until they enrol, so tell them before the release and keep one administrator able to run `reset-mfa`. **owner**

## 5. ML
- [ ] No model is active unless its model card, licence audit and held-out metrics are on file. The 1.0.0 candidate is non-default and its artifact is not shipped in Git.
- [ ] Review rule (low confidence goes to a person) confirmed in the deployed settings.

## 6. Verification on the deployed stack
- [ ] `tests/smoke/smoke.py --api <url> --web <url>` passes.
- [ ] Sign-in, report waste, classification review, collection, rewards redemption, marketplace request, support request and assistant answer exercised once by a person on the real host.
- [ ] Keyboard-only and screen-reader pass on sign-in, reports, assistant and support (automated axe is not a substitute).
- [ ] Live vehicle tracking claimed only after a real device has reported end to end.
- [ ] Health, readiness and log shipping checked; an alert path exists for failures.

## 7. Release
- [ ] Version tag and release notes list what is *not* done (`docs/project-completion/LIMITATIONS.md`).
- [ ] Deployment executed by a person with rollback ready; the deployment and its time are recorded here, not assumed.
