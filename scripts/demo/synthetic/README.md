# Synthetic Hyderabad dataset

A deterministic, labelled, resumable generator that fills a **demonstration or test** database with
the full EcoMind operating chain: citizen → waste report → collection task → assignment → route →
vehicle tracking → collection events → facility recovery → material passport and custody → reward
ledger and redemptions, plus notifications, community incidents and marketplace activity.

Full design, row counts, limitations and the table-by-table coverage are in
[`docs/database/synthetic-data.md`](../../../docs/database/synthetic-data.md). **This data is fiction.**
Coordinates are approximate locality centres, zones are not official wards, people are not real.

## Run it

Run from `scripts/demo` with the application's virtual environment (psycopg 3 and argon2 are already
backend dependencies). The database is taken from `SYNTH_DSN`, `DEMO_DSN` or `DATABASE_URL`.

```bash
cd scripts/demo
python -m synthetic plan     --profile development     # row counts, nothing is written
python -m synthetic load     --profile development     # COPY loader, progress, resumable
python -m synthetic verify   --profile development     # 24 SQL integrity checks
python -m synthetic report   --profile development     # per-table counts (total vs synthetic)
python -m synthetic cleanup  --profile development --yes-delete-synthetic

# real detectors over the loaded history (the generator never invents their output)
ANALYTICS_EMAIL=manager@example.org ANALYTICS_PASSWORD=... python -m synthetic.run_analytics
# dashboard API versus independent SQL (73 figures on the development profile)
MANAGER_EMAIL=manager@example.org MANAGER_PASSWORD=... python -m synthetic.compare_api
```

Flags: `--seed` (default 42), `--anchor` (last day of history, default today in `Asia/Kolkata`),
`--allow-existing-data`, `--allow-remote`, `--confirm-large` (required for `large` and `stress`).
The same seed + profile + anchor always produce the same rows and the same primary keys.

## Profiles

| Profile | Days | Tasks/day | Rows (approx.) | Use |
|---|---|---|---|---|
| `test` | 70 | 7 | 9.7 k | automated tests (`backend/tests/integration/test_synthetic_dataset.py`) |
| `development` | 210 | 10 | 49.8 k | local demonstration; enough weeks (>= 26) for the forecaster |
| `integration` | 270 | 45 | 285 k | integration and query-plan checks |
| `large` | 365 | 230 | 1.81 M | load and index testing; never run automatically |
| `stress` | 730 | 420 | not planned (estimated >= 5 M) | not executed; needs `--confirm-large` and a throw-away database |

## Safety

* Refuses when `ENVIRONMENT` is `production` or `staging`, when the host is not local (unless
  `--allow-remote`), when real facilities or tasks exist (unless `--allow-existing-data`), and when a
  different seed, profile or anchor is already loaded.
* Every synthetic primary key starts with `53594e54-` (ASCII `SYNT`), so a synthetic row is
  recognisable from its id alone; user e-mails use `synthetic.example.org` (reserved); every name,
  zone and facility carries the `[Demo]` label. The accounts have unusable (discarded) passwords.
* `cleanup` deletes only ids with that prefix, needs a superuser (it relaxes append-only triggers for
  the delete) and refuses when a real row references a synthetic one.
