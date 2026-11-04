# Load test report (2026-11-04)

**Scope and honesty.** One run on one sandbox, against the **development** synthetic dataset (about
52 k rows; see [synthetic-data.md](../database/synthetic-data.md)). The load generator, the API (one
uvicorn process, the shipped Dockerfile layout), PostgreSQL and the monitoring all shared the same
2-vCPU Intel Xeon 2.6 GHz VM with 3.9 GB RAM. The numbers therefore **describe this machine and this
data volume only**. They are not a capacity claim for any deployment; repeat on target hardware with
production-like data before quoting anything. Nothing here was run against Docker Compose, a remote
host, or the integration/large profiles.

## Tool and scenario

* Locust 2.47.0, `scripts/perf/locustfile.py` (headless; CSV output). The older closed-loop script
  `scripts/perf/load_test.py` is kept for quick smoke checks.
* Read-only traffic that the screens generate, per role (tokens obtained once per run; the only POSTs
  are four sign-ins): citizens (own reports, unread count, rewards, marketplace, help), collectors
  (own tasks, route plans, unread count), facility operators (recovery, passports), managers
  (overview, weekly trend, reports, tasks, facilities, fleet, incidents, anomalies). User mix 6:2:1:1.
* Two modes: **realistic** (think time 1-3 s per user) and **saturation** (0-0.05 s) to find the limit.
* Resource sampling every 2 s with psutil (API process CPU and RSS, summed PostgreSQL CPU,
  `pg_stat_activity` connection count). `log_min_duration_statement = 100 ms` was set on PostgreSQL;
  `pg_stat_statements` is not available in this build, so there is no per-query table.

## Result after the fixes below

Run: 75 s per level (realistic) and 45 s (saturation). Latency in ms. "CPU" is the average over the run
as a percentage of one core (the API is a single process).

| Mode | Users | Requests | Failures | Req/s | Median | p95 | p99 | Max | API CPU | PG CPU | API RSS (MB) | DB conns (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| realistic | 10 | 366 | 0 | 5.0 | 15 | 31 | 120 | 134 | 6% | 1% | 149 | 10 |
| realistic | 25 | 917 | 0 | 12.4 | 15 | 33 | 80 | 94 | 13% | 3% | 149 | 11 |
| realistic | 50 | 1,796 | 0 | 24.3 | 15 | 37 | 110 | 227 | 23% | 6% | 150 | 13 |
| realistic | 100 | 3,464 | 0 | 46.8 | 17 | 58 | 120 | 170 | 41% | 11% | 152 | 14 |
| saturation | 25 | 5,398 | 0 | 122.8 | 170 | 250 | 300 | 377 | 94% | 25% | 152 | 23 |
| saturation | 50 | 5,185 | 0 | 117.7 | 380 | 500 | 540 | 634 | 94% | 17% | 153 | 35 |
| saturation | 100 | 5,231 | 0 | 118.6 | 790 | 940 | 1,000 | 1,073 | 95% | 19% | 155 | 41 |

Reading it: up to 100 realistic users the API answers in tens of milliseconds with no errors. A single
process saturates at roughly **118-123 requests/s** because the one Python process reaches 95% of its
core; extra users then only queue (latency rises linearly, throughput stays flat, no errors). The
database is not the bottleneck (PostgreSQL averaged under 25% CPU). The slowest endpoint is
`/analytics/overview` (median 46 ms, p95 120 ms at 100 users: it runs about a dozen aggregate queries).
**No application statement exceeded 100 ms** (the PostgreSQL slow-query log contains only the test
suite's `DROP DATABASE`). Memory is flat at about 150 MB.

## Defect found by this test (and fixed)

Before the fix, the 100-user saturation run **stalled**: 243 requests in 45 s, 30 failures, p95 30 s
(every failure a 30 s pool timeout answered as HTTP 500), API CPU near 0% for long stretches. The API
log showed `QueuePool limit of size 5 overflow 10 reached, connection timed out`.

| Before | 100 users, no think | 243 requests, 30 failures, 7.4 req/s, p95 30,000 ms |
|---|---|---|
| Fix 1 only (pool 20+20, 10 s timeout, 503) | 100 users, no think | 1,671 requests, 16 failures (503), 47 req/s, p95 11,000 ms |
| Final | 100 users, no think | **5,231 requests, 0 failures, 118.6 req/s, p95 940 ms** |

Root cause (two parts, both visible in the traces): (1) the engine used SQLAlchemy's default pool of
5 + 10 connections while FastAPI runs synchronous handlers on 40 threads; (2) the synchronous
`get_db` dependency created **and closed** the session on that same thread pool, and authentication
kept its connection across the hand-off to the handler's thread. Threads waiting for a connection
therefore waited on requests that were themselves waiting for a thread, a starvation deadlock
that cleared only when the pool timeout fired. Raising the pool alone (fix 1) reduced but did not remove it.

Fix: `get_db` is now an `async` generator (opening and closing a session never waits for a thread;
closing only returns an idle connection), the authentication dependency commits (ends its read
transaction) before returning so its connection is back in the pool before the handler runs, the pool is
configurable (`DB_POOL_SIZE` 20, `DB_MAX_OVERFLOW` 20, `DB_POOL_TIMEOUT_SECONDS` 10; keep size + overflow >= 40 per
process and within PostgreSQL's `max_connections`), and an exhausted pool answers `503 service_busy` with
`Retry-After` instead of a 500. Tests: `backend/tests/api/test_connection_pool.py` (96 concurrent requests
share a pool of 3; authentication holds no connection; `get_db` is async), `test_error_handling.py`, `test_config.py`.
Mutation checks: removing the commit or making `get_db` synchronous fails the new tests.

Trade-off: closing a session on the event loop does one rollback round trip there. It is sub-millisecond
against a local database; against a distant database it blocks the loop for that round trip, so keep the
database close to the API.

## Not done

* 100-user runs used a single Locust process on the same VM; the generator itself consumed CPU
  (system CPU averaged 70% at saturation), which understates what the API could do on its own cores.
* Multiple API workers, a reverse proxy, TLS, a remote database, the integration/large datasets, write
  traffic (reports, task transitions, uploads), the classification endpoint and a soak test were **not**
  measured. Authentication was exercised only through pre-issued tokens, not through repeated sign-ins
  (sign-in is deliberately rate limited and Argon2id-hashed, so it is CPU heavy by design).
* No numeric targets (SLOs) were set by the owner, so no pass/fail threshold is claimed.

## Reproduce

```bash
python -m venv /tmp/venv-load && /tmp/venv-load/bin/pip install locust
cd scripts/perf
LOAD_PASSWORD='...' /tmp/venv-load/bin/locust -f locustfile.py --headless -u 50 -r 10 -t 75s \
    --host http://localhost:8000 --csv /tmp/locust-50 --only-summary
# saturation: LOAD_THINK_MIN=0 LOAD_THINK_MAX=0.05 ...
```
The accounts are the six demonstration accounts (`citizen@`, `collector@`, `operator@`, `manager@example.org`)
with the demonstration password; override with `LOAD_CITIZEN` etc. The script refuses a non-local host
unless `LOAD_ALLOW_REMOTE=1`.
