# Load testing

`scripts/perf/load_test.py` is a closed-loop load generator for the **read-only** API. It needs no extra
packages (it uses the backend environment's `httpx2`) and writes nothing to the database.

```bash
LOAD_PASSWORD='<password shared by the accounts>' python scripts/perf/load_test.py \
  --login admin@example.org --login manager@example.org --login citizen@example.org \
  --concurrency 20 --duration 30 --json /tmp/load.json --max-p95-ms 500 --max-error-rate 0.01
```

- It signs each `--login` account in once, then probes every endpoint with every account and keeps the pairs
  that answer 2xx (a role that may not read an endpoint is not counted as a failure; an endpoint nobody may read
  is printed as **skipped**, never as a pass).
- Then `--concurrency` virtual users send weighted random reads (lists, analytics, notifications, health)
  for `--duration` seconds. Errors during the run (non-2xx or timeouts) are counted; p50/p95/p99 are per
  endpoint and overall.
- It refuses a non-local `--base-url` unless `--allow-remote` is given. Never aim it at a system you do not run.
- Exit status 1 when `--max-p95-ms` or `--max-error-rate` is exceeded (usable as a pipeline gate later).
- `tests/contract/test_load_test_script.py` checks that every endpoint in the scenario exists in the real API.

## Result (sandbox only: not a capacity statement)

Run 2026-10-21 in the development sandbox: **2 vCPU, ~3.9 GB RAM, the load generator, one uvicorn worker
(no `--workers`), PostgreSQL 16 and two Vite dev servers all on the same machine**, the small demonstration
data set (a handful of rows per table, no photos). Python 3.11.

| Virtual users | Duration | Requests | Throughput | Errors | p50 | p95 | p99 |
|---|---|---|---|---|---|---|---|
| 10 | 30 s | 3,913 | 130 req/s | 0.00 % | 73.7 ms | 122.9 ms | 164.2 ms |
| 50 | 30 s | 3,702 | 122 req/s | 0.00 % | 417.7 ms | 639.3 ms | 780.4 ms |

Reading it: with one worker process the API saturates at roughly 125-130 requests/s on this machine, and
the generator itself competes for the same two CPUs. Beyond saturation latency rises in proportion to the
number of users (queueing), with no errors and no timeouts up to 50 users. Per endpoint at 10 users, list reads
were 73-77 ms median (p95 about 100 ms), `/health` 22 ms and `/analytics/overview` 124 ms (p95 167 ms).

**What this does not show.** Nothing here applies to a real deployment: different hardware, several workers,
network latency, a TLS-terminating proxy, production-sized tables (thousands of reports, a year of vehicle
location events), image uploads, classification inference (CPU heavy; not in the scenario), writes, or the
Argon2id sign-in cost (deliberately slow; a burst of sign-ins is not modelled). No target was set by the
project, so there is no pass or fail verdict. **Load testing on the target hardware with realistic data
remains to be done before any public launch.**

## Suggested next steps (not done)

1. Agree numbers with the owner: expected concurrent users, the p95 target (for example 500 ms for list reads).
2. Run the script on the deployment host with `--workers N` (one per CPU) behind the real proxy.
3. Load the database with production-like volumes first (`scripts/demo/seed_demo.py` is for a small demo).
4. Add classification and sign-in scenarios and a write mix in a separate run against a throw-away database.
