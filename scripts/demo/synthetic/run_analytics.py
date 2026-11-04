"""Run the REAL forecasting and anomaly detectors over every series that has enough history.

The synthetic dataset only provides the weekly collected-weight history; the forecasts and the
anomaly flags are produced by the application's own algorithms through its API, exactly as an
operator would trigger them. A series that is too short answers 422 `insufficient_history`.

    ANALYTICS_EMAIL=manager@example.org ANALYTICS_PASSWORD=... python -m synthetic.run_analytics
(run from scripts/demo; API defaults to http://localhost:8000 and must be local)
"""

from __future__ import annotations

import os
import sys

try:
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx


def main() -> int:
    api = os.environ.get("DEMO_API", "http://localhost:8000")
    if not api.startswith(("http://localhost", "http://127.0.0.1")):
        print("Refusing to run against a non-local API", file=sys.stderr)
        return 2
    base = api + "/api/v1"
    login = httpx.post(f"{base}/auth/login", json={"email": os.environ["ANALYTICS_EMAIL"], "password": os.environ["ANALYTICS_PASSWORD"]})
    login.raise_for_status()
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    series = httpx.get(f"{base}/forecasting/series", headers=headers, timeout=60)
    series.raise_for_status()
    for item in series.json():
        for path, body in (
            ("/forecasting/forecasts", {"series": item["ref"], "horizon_weeks": 4, "save": True}),
            ("/anomalies/scan", {"series": item["ref"], "lookback_weeks": 104}),
        ):
            r = httpx.post(f"{base}{path}", headers=headers, json=body, timeout=120)
            print(f"{path:<24}{item['ref']:<28}{r.status_code}{'  ' + r.text[:120] if r.status_code >= 400 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
