#!/usr/bin/env python3
"""Smoke test for a running stack. Exit code 0 only if everything answers correctly.

    python tests/smoke/smoke.py --api http://localhost:8000 --web http://localhost:5173 --wait 60

Checks: API /health (liveness), API /ready (database reachable and schema at head), and that the
frontend serves its HTML. Uses only the standard library.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def fetch(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - operator-supplied URL
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def check(api: str, web: str | None) -> list[str]:
    failures: list[str] = []
    try:
        status, body = fetch(f"{api}/health")
        if status != 200 or json.loads(body).get("status") != "ok":
            failures.append(f"/health returned {status}: {body[:200]}")
        status, body = fetch(f"{api}/ready")
        if status != 200 or json.loads(body).get("status") != "ready":
            failures.append(f"/ready returned {status}: {body[:300]}")
        if web:
            status, body = fetch(web)
            if status != 200 or '<div id="root">' not in body:
                failures.append(f"frontend {web} did not serve the app shell (status {status})")
    except (urllib.error.URLError, OSError, ValueError) as error:
        failures.append(f"request failed: {error}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--web", default=None, help="frontend origin (optional)")
    parser.add_argument("--wait", type=int, default=0, help="retry for up to N seconds")
    args = parser.parse_args()

    deadline = time.monotonic() + args.wait
    while True:
        failures = check(args.api.rstrip("/"), args.web.rstrip("/") if args.web else None)
        if not failures or time.monotonic() >= deadline:
            break
        time.sleep(2)
    for failure in failures:
        print(f"FAIL {failure}")
    if not failures:
        print("smoke ok")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
