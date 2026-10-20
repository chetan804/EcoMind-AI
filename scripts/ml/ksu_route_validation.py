"""Validate the route optimiser against a real routing benchmark (read-only, deterministic).

Data: Kalasin University campus waste collection (Thailand): road-distance matrix between 23
nodes and the five routes actually driven on five days (git-ignored checkout pinned in
``docs/ml/dataset-research``). Each day visits a different subset of the 21 collection points,
starting at the depot (node 1), ending at the disposal point (node 23) and returning to the depot.

For every day the script reports, on REAL road distances (metres):
  * observed  : the length of the route that was actually driven,
  * optimal   : the exact optimum for that day's stops (Held-Karp),
  * heuristic : what the product heuristic finds given the road matrix,
  * straight  : the route the PRODUCT would plan from coordinates alone (great-circle distances),
                evaluated on the real road matrix,
and the relationship between great-circle and road distance over all 253 node pairs.

    PYTHONPATH=backend python scripts/ml/ksu_route_validation.py
"""

from __future__ import annotations

import csv
import json
import statistics
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend"))

from app.modules.route_planning import optimizer as opt

SRC = REPO / "datasets" / "external" / "ksu-routing-src"
PINNED = "1653571d"
OUT = (
    REPO
    / "docs"
    / "ml"
    / "dataset-research"
    / "experiments"
    / "route-validation-ksu.json"
)
DEPOT, DISPOSAL = 1, 23


def main() -> int:
    head = subprocess.run(
        ["git", "-C", str(SRC), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not head.startswith(PINNED):
        raise SystemExit(f"ksu-routing-src is at {head}, expected {PINNED}…")
    with (SRC / "data" / "nodes.csv").open(newline="") as handle:
        nodes = {
            int(r["node_id"]): (float(r["latitude"]), float(r["longitude"]))
            for r in csv.DictReader(handle)
        }
    ids = sorted(nodes)
    index = {node: i for i, node in enumerate(ids)}
    road = np.zeros((len(ids), len(ids)))
    with (SRC / "data" / "distance_pairs.csv").open(newline="") as handle:
        for r in csv.DictReader(handle):
            a, b = index[int(r["from_node"])], index[int(r["to_node"])]
            road[a, b] = road[b, a] = float(r["distance_m"])
    straight = opt.haversine_matrix([nodes[i] for i in ids])
    iu = np.triu_indices(len(ids), 1)
    ratio = road[iu] / straight[iu]
    pair_stats = {
        "pairs": len(ratio),
        "road_over_straight_min": float(np.min(ratio)),
        "road_over_straight_median": float(np.median(ratio)),
        "road_over_straight_max": float(np.max(ratio)),
        "pearson_r": float(np.corrcoef(road[iu], straight[iu])[0, 1]),
        "straight_ever_longer_than_road": int(np.sum(straight[iu] > road[iu] + 1e-6)),
    }
    days = []
    with (SRC / "data" / "observed_routes.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        seq = [int(x) for x in row["sequence_driven"].split("-")]
        assert seq[0] == DEPOT and seq[-1] == DEPOT and seq[-2] == DISPOSAL
        stops = [index[n] for n in seq[1:-2]]
        depot, final = index[DEPOT], index[DISPOSAL]
        observed = opt.route_length(road, depot, [index[n] for n in seq[1:-2]], final)
        optimal = opt.optimize(
            road, depot=depot, stops=stops, final=final, exact_limit=22
        )
        heur = opt.optimize(road, depot=depot, stops=stops, final=final, exact_limit=0)
        nn = opt.route_length(
            road, depot, opt._nearest_neighbour(road, depot, stops), final
        )
        plan = opt.optimize(
            straight, depot=depot, stops=stops, final=final, exact_limit=22
        )
        plan_on_road = opt.route_length(road, depot, plan.order, final)
        days.append(
            {
                "day": row["day"],
                "stops": len(stops),
                "observed_m": observed,
                "optimal_m": optimal.length,
                "heuristic_m": heur.length,
                "nearest_neighbour_m": nn,
                "straight_line_plan_on_road_m": plan_on_road,
                "observed_over_optimal": observed / optimal.length,
                "heuristic_over_optimal": heur.length / optimal.length,
                "nearest_neighbour_over_optimal": nn / optimal.length,
                "straight_line_plan_over_optimal": plan_on_road / optimal.length,
                "optimal_method": optimal.method,
                "optimal_order_nodes": [ids[i] for i in optimal.order],
            }
        )
        print(
            row["day"],
            len(stops),
            f"obs {observed:.0f} opt {optimal.length:.0f} heur {heur.length:.0f} "
            f"straight-plan {plan_on_road:.0f}",
            flush=True,
        )
    summary = {
        key: statistics.mean(d[key] for d in days)
        for key in (
            "observed_over_optimal",
            "heuristic_over_optimal",
            "nearest_neighbour_over_optimal",
            "straight_line_plan_over_optimal",
        )
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "source": "kamthornsa/ksu-waste-collection-dataset",
                "commit": head,
                "optimizer": f"{opt.OPTIMIZER_NAME} {opt.OPTIMIZER_VERSION}",
                "days": days,
                "mean_ratios": summary,
                "pair_distance_stats": pair_stats,
                "n_days": len(days),
                "caveat": "five days on one small campus: indicative, not statistically strong",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
