"""Command line: plan | load | verify | report | cleanup. See README.md."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time

from . import loader
from .profiles import PROFILES
from .world import IST, World


def _anchor(text: str) -> dt.date:
    if text == "today":
        return dt.datetime.now(IST).date()
    return dt.date.fromisoformat(text)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="synthetic", description=__doc__)
    p.add_argument("command", choices=("plan", "load", "verify", "report", "cleanup"))
    p.add_argument("--profile", choices=sorted(PROFILES), default="development")
    p.add_argument("--seed", type=int, default=42, help="same seed + profile + anchor = same data")
    p.add_argument("--anchor", default="today", help="last day of history (YYYY-MM-DD or 'today', Asia/Kolkata)")
    p.add_argument("--allow-existing-data", action="store_true", help="add next to non-synthetic facilities/tasks")
    p.add_argument("--allow-remote", action="store_true", help="permit a non-local database host (throw-away databases only)")
    p.add_argument("--yes-delete-synthetic", action="store_true", help="required by cleanup")
    p.add_argument("--confirm-large", action="store_true", help="required for the large and stress profiles")
    a = p.parse_args(argv)

    profile = PROFILES[a.profile]
    anchor = _anchor(a.anchor)
    world = World.build(a.seed, profile, anchor)
    print(f"profile={profile.name} seed={a.seed} anchor={anchor} days={profile.days} (target {profile.approx_rows} rows)")

    try:
        if a.command == "plan":
            t0 = time.monotonic()
            counts = loader.count_rows(world)
            for table, n in counts.items():
                print(f"  {table:<34}{n:>12,}")
            print(f"  {'TOTAL (+ dimension rows)':<34}{sum(counts.values()):>12,}   [{time.monotonic() - t0:.0f}s, nothing written]")
            return 0
        if a.command in ("load", "cleanup") and a.profile in ("large", "stress") and a.command == "load" and not a.confirm_large:
            raise loader.Refused(f"The {a.profile} profile is big; pass --confirm-large if this machine and database can take it.")
        conn = loader.connect(loader.dsn_from_environment())
        try:
            if a.command == "load":
                loader.guard(conn, world, allow_existing=a.allow_existing_data, allow_remote=a.allow_remote)
                added = loader.load_dimensions(conn, world)
                print("dimensions added:", {k: v for k, v in added.items() if v} or "none (already present)")
                t0 = time.monotonic()
                totals = loader.load(conn, world)
                print(f"loaded {sum(totals.values()):,} rows in {time.monotonic() - t0:.0f}s: ", {k: v for k, v in totals.items() if v})
                return 0
            if a.command == "verify":
                failed = 0
                for name, bad in loader.run_checks(conn):
                    print(f"  {'PASS' if bad == 0 else 'FAIL'}  {name}" + ("" if bad == 0 else f"  ({bad} rows)"))
                    failed += bad != 0
                print("all checks passed" if not failed else f"{failed} check(s) FAILED")
                return 1 if failed else 0
            if a.command == "report":
                print(f"  {'table':<34}{'total':>12}{'synthetic':>12}")
                rows = loader.table_counts(conn)
                for name, total, synthetic in rows:
                    print(f"  {name:<34}{total:>12,}{synthetic:>12,}")
                print(f"  {'ALL TABLES':<34}{sum(r[1] for r in rows):>12,}{sum(r[2] for r in rows):>12,}")
                return 0
            if a.command == "cleanup":
                if not a.yes_delete_synthetic:
                    raise loader.Refused("Cleanup deletes every row whose id starts with 53594e54-. Re-run with --yes-delete-synthetic.")
                loader.cleanup(conn, allow_remote=a.allow_remote)
                return 0
        finally:
            conn.close()
    except loader.Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0
