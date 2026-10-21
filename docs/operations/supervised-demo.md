# Running a supervised demonstration

Release target recorded by the owner: a **supervised demonstration or academic submission**. This is
not a public production deployment. The build environment had no Docker, so the `make` and Compose
steps below were **not run**; the `python -m app.cli` commands and the smoke script were run against a
host-based stack (same code, PostgreSQL and uvicorn without containers). Your first run is the rehearsal.

Do **not** expose this stack to the Internet. It uses the local development Compose file
(`ENVIRONMENT=local`), the console or Mailpit e-mail backend and well-known demo account names.

## Before the audience arrives (about 15 minutes)

1. `make env` (creates `.env` files with generated secrets; never overwrites).
2. `make demo-mail-up` (stack plus a Mailpit inbox at http://localhost:8025; creates `.env.demo-mail`).
   Plain `make up` also works; then e-mails appear in `docker compose logs backend`.
   The CI browser tests use the same Mailpit set-up (see `docs/operations/account-recovery.md`).
3. Load the help articles once: `docker compose exec backend python -m app.cli seed-support-knowledge`.
   Without them the assistant answers "no answer" to everything (the browser suite fails for this reason on an empty database).
4. Create the demo people (password of your choice, 12 or more characters; change it any time by re-running with `--reset-passwords`):
   `docker compose exec -e DEMO_PASSWORD='<your password>' backend python -m app.cli seed-demo-accounts`
   gives `admin@`, `manager@`, `collector@`, `operator@`, `citizen@`, `verifier@example.org`, already verified.
5. Optional demonstration records (facilities, vehicles, reports, all invented and labelled): `scripts/demo/seed_demo.py`
   against a throw-away database only; it is not idempotent. Reference series: `python -m app.cli import-reference-series --key austin`.
6. Optional real base map: follow `docs/maps/OFFLINE_MAPS.md` (the owner downloads the MapTiler file, then
   `python scripts/maps/mbtiles_to_pmtiles.py <file>.mbtiles`). Without it the map shows markers on a plain background and says so.
7. Open http://localhost:5173 and run `python3 tests/smoke/smoke.py --api http://localhost:8000 --web http://localhost:5173`.

## What to say about what you will see

* The waste classifier has **no active model** unless you register and activate one; the candidate `1.0.0` is trained on TrashNet only and
  reaches 0.45 accuracy on real facility photos (`docs/ml/dataset-research/DATASET_SELECTION_REPORT.md`). Say that plainly; the review
  queue is the safety net.
* Vehicle positions are shown as live only when a real device has reported; simulated points are labelled as simulation.
* The help assistant quotes help articles and the person's own records; it does not generate text.
* Two-step sign-in is enforced for administrators and managers only when `ENVIRONMENT=production`; in this local stack it is optional.
* Google Maps and road routing are off by default (offline map, no routing).

## After the demonstration

`make demo-mail-down` stops the stack. `docker compose down -v` also deletes the database and uploads (destructive; only for a throw-away demo).

## Going beyond a demonstration

Use `docs/operations/runbook.md` ("Deploying") and `docs/project-completion/RELEASE_CHECKLIST.md`. Open items that block a public launch are in
`docs/project-completion/LIMITATIONS.md` and the owner decisions in `DECISION_LOG.md`.
