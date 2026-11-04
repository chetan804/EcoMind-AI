"""Reconcile the dashboard API with independent SQL over the same database.

Every figure the Command Center shows comes from `/analytics/overview` and
`/analytics/weekly-trend`. This script fetches both through the API, recomputes each figure with
plain SQL (no application code), using the window the API reports (`window_start`), and prints
one PASS/FAIL line per figure. Exit code 1 when anything differs.

    MANAGER_EMAIL=manager@example.org MANAGER_PASSWORD=... python -m synthetic.compare_api

(run from scripts/demo; DSN from SYNTH_DSN / DEMO_DSN / DATABASE_URL; API must be local.)
"""

from __future__ import annotations

import datetime as dt
import decimal
import os
import sys

import psycopg

try:
    import httpx
except ImportError:  # pragma: no cover
    import httpx2 as httpx

from synthetic.loader import dsn_from_environment

D = decimal.Decimal


def main() -> int:
    api = os.environ.get("DEMO_API", "http://localhost:8000")
    if not api.startswith(("http://localhost", "http://127.0.0.1")):
        print("Refusing to run against a non-local API", file=sys.stderr)
        return 2
    base = api + "/api/v1"
    login = httpx.post(
        f"{base}/auth/login",
        json={"email": os.environ["MANAGER_EMAIL"], "password": os.environ["MANAGER_PASSWORD"]},
    )
    login.raise_for_status()
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    weeks = 12
    # Fetch both before querying, so the two views are as close in time as possible.
    ov = httpx.get(f"{base}/analytics/overview?days=30", headers=headers, timeout=60).json()
    trend = httpx.get(f"{base}/analytics/weekly-trend?weeks={weeks}", headers=headers, timeout=60).json()
    start = dt.datetime.fromisoformat(ov["window_start"].replace("Z", "+00:00"))

    failures = 0
    with psycopg.connect(dsn_from_environment()) as conn:

        def one(sql: str, *params: object) -> object:
            row = conn.execute(sql, params or None).fetchone()
            assert row is not None
            return row[0]

        def check(name: str, api_value: object, sql_value: object) -> None:
            nonlocal failures
            try:
                same = D(str(api_value)) == D(str(sql_value))
            except decimal.InvalidOperation:
                same = api_value == sql_value
            failures += 0 if same else 1
            print(f"{'PASS' if same else 'FAIL'}  {name:<46} api={api_value!s:<14} sql={sql_value}")

        check("reports.total", ov["reports"]["total"], one("select count(*) from waste_reports"))
        check("reports.in_window", ov["reports"]["in_window"], one("select count(*) from waste_reports where created_at >= %s", start))
        for item in ov["reports"]["by_status"]:
            check(f"reports.{item['key']}", item["count"], one("select count(*) from waste_reports where status = %s", item["key"]))
        check("tasks_total", ov["collection"]["tasks_total"], one("select count(*) from collection_tasks"))
        for item in ov["collection"]["by_status"]:
            check(f"tasks.{item['key']}", item["count"], one("select count(*) from collection_tasks where status = %s", item["key"]))
        check("tasks.open", ov["collection"]["open_tasks"], one("select count(*) from collection_tasks where status in ('pending','assigned','in_progress')"))
        check("collected_kg_total", ov["collection"]["collected_weight_kg_total"], one("select coalesce(sum(collected_weight_kg),0) from collection_events where event_type='collected'"))
        check("collected_kg_in_window", ov["collection"]["collected_weight_kg_in_window"], one("select coalesce(sum(collected_weight_kg),0) from collection_events where event_type='collected' and occurred_at >= %s", start))
        check("completed_in_window (distinct tasks)", ov["collection"]["completed_in_window"], one("select count(distinct collection_task_id) from collection_events where event_type='collected' and occurred_at >= %s", start))
        check("vehicles_total", ov["fleet"]["vehicles_total"], one("select count(*) from fleet_vehicles"))
        check("capacity_kg_available", ov["fleet"]["capacity_kg_available"], one("select coalesce(sum(capacity_kg),0) from fleet_vehicles where status in ('available','in_service')"))
        check("facilities.total", ov["facilities"]["total"], one("select count(*) from facilities"))
        check("facilities.active", ov["facilities"]["active"], one("select count(*) from facilities where status='active'"))
        check("incidents.total", ov["incidents"]["total"], one("select count(*) from community_incidents"))
        check("incidents.open", ov["incidents"]["open_incidents"], one("select count(*) from community_incidents where status in ('open','acknowledged','in_progress')"))
        check("recovery.verified", ov["recovery"]["verified_records"], one("select count(*) from recovery_records where verification_status='verified'"))
        check("recovery.pending", ov["recovery"]["pending_records"], one("select count(*) from recovery_records where verification_status='pending'"))
        check("recovery.input_kg (verified)", ov["recovery"]["input_weight_kg"], one("select coalesce(sum(input_weight_kg),0) from recovery_records where verification_status='verified'"))
        check("recovery.recovered_kg (verified)", ov["recovery"]["recovered_weight_kg"], one("select coalesce(sum(recovered_weight_kg),0) from recovery_records where verification_status='verified'"))
        check("rewards.entries", ov["rewards"]["entries"], one("select count(*) from reward_ledger_entries"))
        check("rewards.users", ov["rewards"]["users"], one("select count(distinct user_id) from reward_ledger_entries"))
        check("rewards.net_points", ov["rewards"]["net_points"], one("select coalesce(sum(points),0) from reward_ledger_entries"))
        check("anomalies.open (operational series)", ov["anomalies"]["open_alerts"], one("select count(*) from anomaly_alerts where metric not like 'reference:%%' and status='open'"))
        check("passports.total", ov["passports"]["total"], one("select count(*) from material_passports"))
        for item in ov["passports"]["by_status"]:
            check(f"passports.{item['key']}", item["count"], one("select count(*) from material_passports where status=%s", item["key"]))
        for p in trend["points"]:
            monday = p["week_start"]
            lo = dt.datetime.fromisoformat(monday).replace(tzinfo=dt.UTC)
            hi = lo + dt.timedelta(days=7)
            check(f"week {monday} kg", p["collected_weight_kg"], one("select coalesce(sum(collected_weight_kg),0) from collection_events where event_type='collected' and occurred_at >= %s and occurred_at < %s", lo, hi))
            check(f"week {monday} tasks", p["tasks_completed"], one("select count(distinct collection_task_id) from collection_events where event_type='collected' and occurred_at >= %s and occurred_at < %s", lo, hi))
            check(f"week {monday} reports", p["reports_submitted"], one("select count(*) from waste_reports where created_at >= %s and created_at < %s", lo, hi))

    print(f"\n{'ALL FIGURES AGREE' if not failures else str(failures) + ' FIGURE(S) DIFFER'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
