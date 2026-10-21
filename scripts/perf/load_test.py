#!/usr/bin/env python3
"""Closed-loop load test of the read-only API (developer tooling; no extra dependencies).

Signs in a few accounts once, then runs C concurrent virtual users for D seconds. Each user picks
read-only endpoints at random (weights below) with the role-appropriate token and records latency
and status. It writes nothing to the database (no POSTs besides the initial sign-ins).

  LOAD_PASSWORD='...' python scripts/perf/load_test.py --login admin@example.org \
      --login citizen@example.org --concurrency 20 --duration 30

Refuses a target that is not local unless --allow-remote is given (never point it at a system you
do not run; sign-in is rate limited and the test would look like an attack).

The result describes THIS machine, THIS database size and THIS process layout only. Numbers from a
laptop or a CI-style sandbox are not capacity claims for a deployment: repeat on the target hardware
with production-like data before quoting anything. Exit status 1 when --max-p95-ms or
--max-error-rate is exceeded, so it can gate a pipeline later.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import sys
import time
from collections import defaultdict
from urllib.parse import urlparse

try:  # the backend's dev environment ships `httpx2`; an older environment may have `httpx`
    import httpx2 as httpx
except ImportError:
    import httpx

# (path, weight, needs a sign-in). Listing/summary reads that the screens actually make.
ENDPOINTS: list[tuple[str, int, bool]] = [
    ("/health", 2, False),
    ("/ready", 2, False),
    ("/api/v1/waste-reports?page=1&page_size=20", 6, True),
    ("/api/v1/facilities?page=1&page_size=20", 4, True),
    ("/api/v1/fleet/vehicles?page=1&page_size=20", 3, True),
    ("/api/v1/collection/tasks?page=1&page_size=20", 4, True),
    ("/api/v1/notifications/unread-count", 6, True),
    ("/api/v1/analytics/overview", 3, True),
    ("/api/v1/analytics/weekly-trend", 2, True),
    ("/api/v1/community-incidents?page=1&page_size=20", 2, True),
    ("/api/v1/marketplace/listings?page=1&page_size=20", 2, True),
    ("/api/v1/support/articles?page=1&page_size=20", 2, True),
    ("/api/v1/rewards/catalog", 1, True),
]
LOCAL = {"localhost", "127.0.0.1", "::1"}


def percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return float("nan")
    index = min(len(sorted_values) - 1, max(0, round(fraction * (len(sorted_values) - 1))))
    return sorted_values[index]


async def sign_in(client: httpx.AsyncClient, email: str, password: str) -> str:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if response.status_code != 200:
        raise SystemExit(f"sign-in failed for {email}: HTTP {response.status_code}")
    body = response.json()
    if "access_token" not in body:
        raise SystemExit(f"{email} needs a second step (two-step verification); use another account")
    return body["access_token"]


async def probe(
    client: httpx.AsyncClient, tokens: list[str]
) -> tuple[list[tuple[str, int, list[str]]], list[str]]:
    """One request per endpoint and account: keep the pairs that answer 2xx.

    A role that is not allowed to read an endpoint (403) is not an error of the system under test,
    so such pairs are left out of the run; an endpoint nobody may read, or that does not exist, is
    listed as skipped (never silently counted as a pass). Errors DURING the run are still counted.
    """
    plan: list[tuple[str, int, list[str]]] = []
    skipped: list[str] = []
    for path, weight, needs_token in ENDPOINTS:
        usable = [""] if not needs_token else []
        for token in tokens if needs_token else []:
            response = await client.get(path, headers={"Authorization": f"Bearer {token}"})
            if 200 <= response.status_code < 300:
                usable.append(token)
        if usable:
            plan.append((path, weight, usable))
        else:
            skipped.append(path)
    return plan, skipped


async def worker(
    client: httpx.AsyncClient,
    plan: list[tuple[str, int, list[str]]],
    deadline: float,
    samples: dict[str, list[float]],
    statuses: dict[str, dict[int, int]],
    rng: random.Random,
) -> None:
    weights = [item[1] for item in plan]
    while time.perf_counter() < deadline:
        path, _, usable = rng.choices(plan, weights)[0]
        token = rng.choice(usable)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        started = time.perf_counter()
        try:
            response = await client.get(path, headers=headers)
            code = response.status_code
        except httpx.HTTPError:
            code = 0  # transport failure / timeout
        elapsed_ms = (time.perf_counter() - started) * 1000
        samples[path].append(elapsed_ms)
        statuses[path][code] = statuses[path].get(code, 0) + 1


async def run(args: argparse.Namespace) -> dict[str, object]:
    password = os.environ.get("LOAD_PASSWORD", "")
    if args.login and not password:
        raise SystemExit("set LOAD_PASSWORD (one password shared by the --login accounts)")
    limits = httpx.Limits(max_connections=args.concurrency + 5)
    async with httpx.AsyncClient(base_url=args.base_url, timeout=args.timeout, limits=limits) as client:
        tokens = [await sign_in(client, email, password) for email in args.login]
        plan, skipped = await probe(client, tokens)
        if not plan:
            raise SystemExit("no endpoint answered 2xx; nothing to test")
        samples: dict[str, list[float]] = defaultdict(list)
        statuses: dict[str, dict[int, int]] = defaultdict(dict)
        rng = random.Random(args.seed)
        started = time.perf_counter()
        deadline = started + args.duration
        await asyncio.gather(
            *(
                worker(client, plan, deadline, samples, statuses, random.Random(rng.random()))
                for _ in range(args.concurrency)
            )
        )
        wall = time.perf_counter() - started
    rows = []
    for path in sorted(samples):
        values = sorted(samples[path])
        bad = sum(n for code, n in statuses[path].items() if not 200 <= code < 300)
        rows.append(
            {
                "path": path,
                "requests": len(values),
                "errors": bad,
                "statuses": statuses[path],
                "p50_ms": round(statistics.median(values), 1),
                "p95_ms": round(percentile(values, 0.95), 1),
                "p99_ms": round(percentile(values, 0.99), 1),
                "max_ms": round(values[-1], 1),
            }
        )
    everything = sorted(v for values in samples.values() for v in values)
    total_errors = sum(int(r["errors"]) for r in rows)
    return {
        "base_url": args.base_url,
        "concurrency": args.concurrency,
        "duration_s": round(wall, 1),
        "requests": len(everything),
        "requests_per_second": round(len(everything) / wall, 1),
        "error_rate": round(total_errors / max(1, len(everything)), 4),
        "p50_ms": round(statistics.median(everything), 1),
        "p95_ms": round(percentile(everything, 0.95), 1),
        "p99_ms": round(percentile(everything, 0.99), 1),
        "skipped_endpoints": skipped,
        "endpoints": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--login", action="append", default=[], help="account e-mail (repeatable)")
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--duration", type=float, default=30.0, help="seconds")
    parser.add_argument("--timeout", type=float, default=15.0, help="per-request seconds")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--json", help="also write the result to this file")
    parser.add_argument("--max-p95-ms", type=float)
    parser.add_argument("--max-error-rate", type=float)
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args(argv)
    host = urlparse(args.base_url).hostname or ""
    if host not in LOCAL and not args.allow_remote:
        raise SystemExit(f"refusing to load-test {host}: not local (use --allow-remote only for a system you own)")
    if args.concurrency < 1 or args.duration <= 0:
        raise SystemExit("--concurrency and --duration must be positive")

    result = asyncio.run(run(args))
    print(
        f"{result['requests']} requests in {result['duration_s']} s with {result['concurrency']} users: "
        f"{result['requests_per_second']} req/s, errors {float(str(result['error_rate'])) * 100:.2f}%, "
        f"p50 {result['p50_ms']} ms, p95 {result['p95_ms']} ms, p99 {result['p99_ms']} ms"
    )
    print(f"{'endpoint':52} {'n':>6} {'err':>4} {'p50':>7} {'p95':>7} {'p99':>7} {'max':>8}")
    for row in result["endpoints"]:  # type: ignore[attr-defined]
        print(
            f"{row['path'][:52]:52} {row['requests']:>6} {row['errors']:>4} "
            f"{row['p50_ms']:>7} {row['p95_ms']:>7} {row['p99_ms']:>7} {row['max_ms']:>8}"
        )
    for path in result["skipped_endpoints"]:  # type: ignore[attr-defined]
        print(f"skipped (no account may read it, or it does not exist): {path}")
    if args.json:
        with open(args.json, "w") as handle:
            json.dump(result, handle, indent=2)
    failed = False
    if args.max_p95_ms is not None and float(str(result["p95_ms"])) > args.max_p95_ms:
        print(f"FAIL p95 {result['p95_ms']} ms exceeds {args.max_p95_ms} ms", file=sys.stderr)
        failed = True
    if args.max_error_rate is not None and float(str(result["error_rate"])) > args.max_error_rate:
        print(f"FAIL error rate {result['error_rate']} exceeds {args.max_error_rate}", file=sys.stderr)
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
