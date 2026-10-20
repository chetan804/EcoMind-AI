"""Deterministic route ordering (pure computation: no database, no network).

Problem: one vehicle leaves the ``depot`` (index 0), visits every stop once, optionally ends at a
``final`` node (a disposal/processing facility), and returns to the depot. The objective is the
total distance. This is the path-type travelling-salesman problem.

* ``exact``: Held-Karp dynamic programming, optimal, practical up to ~16 stops (memory
  2^n x n floats). Used automatically for small plans.
* ``heuristic``: nearest neighbour + 2-opt + Or-opt with a fixed number of seeded random
  restarts. Not guaranteed optimal; same input and seed always give the same route.

Distances come from ``haversine_matrix`` (great-circle). That is usually shorter than the road
distance but not always (9 of 253 pairs in the KSU benchmark were longer), so it is an
approximation, never a guarantee. No road
network, traffic, time windows or vehicle capacity are modelled here; see
``docs/api/route-planning-api.md`` for what that means for the plan.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np
from numpy.typing import NDArray

EARTH_RADIUS_M = 6_371_008.8  # IUGG mean Earth radius
EXACT_LIMIT = 12  # stops; above this the heuristic is used unless the caller raises the limit
RESTARTS = 24
SEED = 20261020
OPTIMIZER_NAME = "route-order"
OPTIMIZER_VERSION = "1.0.0"

Matrix = NDArray[np.float64]
Rows = Sequence[Sequence[float]]  # plain nested lists are much faster than numpy scalars
Distances = Matrix | Rows


@dataclass(frozen=True)
class RouteResult:
    order: list[int]  # stop indices in visiting order (depot and final excluded)
    length: float  # same unit as the matrix
    method: str  # "exact_held_karp" | "nn_2opt_oropt" | "trivial"
    legs: list[float]  # depot->first, ..., last->final (if any), ->depot


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def haversine_matrix(points: Sequence[tuple[float, float]]) -> Matrix:
    n = len(points)
    out = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            out[i, j] = out[j, i] = haversine_m(*points[i], *points[j])
    return out


def _sequence(depot: int, order: Sequence[int], final: int | None) -> list[int]:
    return [depot, *order, *([final] if final is not None else []), depot]


def route_length(dist: Distances, depot: int, order: Sequence[int], final: int | None) -> float:
    seq = _sequence(depot, order, final)
    return float(sum(dist[a][b] for a, b in pairwise(seq)))


def _legs(dist: Distances, depot: int, order: Sequence[int], final: int | None) -> list[float]:
    seq = _sequence(depot, order, final)
    return [float(dist[a][b]) for a, b in pairwise(seq)]


def exact(dist: Matrix, depot: int, stops: Sequence[int], final: int | None) -> list[int]:
    """Optimal visiting order (Held-Karp). ``stops`` must not contain depot or final."""
    n = len(stops)
    if n <= 1:
        return list(stops)
    s = list(stops)
    # tail[i]: cost to leave stop i for the end of the route.
    tail = np.array(
        [
            dist[s[i], final] + dist[final, depot] if final is not None else dist[s[i], depot]
            for i in range(n)
        ]
    )
    full = 1 << n
    inf = float("inf")
    best = np.full((full, n), inf)
    parent = np.full((full, n), -1, dtype=np.int16)
    for i in range(n):
        best[1 << i, i] = dist[depot, s[i]]
    sub = np.array([[dist[s[i], s[j]] for j in range(n)] for i in range(n)])
    masks = np.arange(full)
    for size in range(2, n + 1):
        # all masks with exactly `size` bits, processed together (vectorised over masks)
        popcount = np.zeros(full, dtype=np.int8)
        for i in range(n):
            popcount += ((masks >> i) & 1).astype(np.int8)
        layer = masks[popcount == size]
        for j in range(n):
            has_j = layer[(layer >> j) & 1 == 1]
            prev = has_j ^ (1 << j)
            cand = np.full((len(has_j), n), inf)
            for i in range(n):
                if i == j:
                    continue
                ok = (prev >> i) & 1 == 1
                cand[ok, i] = best[prev[ok], i] + sub[i, j]
            arg = np.argmin(cand, axis=1)
            val = cand[np.arange(len(has_j)), arg]
            best[has_j, j] = val
            parent[has_j, j] = arg.astype(np.int16)
    last_mask = full - 1
    end_cost = best[last_mask] + tail
    j = int(np.argmin(end_cost))  # ties -> lowest index: deterministic
    order: list[int] = []
    mask = last_mask
    while j >= 0:
        order.append(s[j])
        prev_j = int(parent[mask, j])
        mask ^= 1 << j
        j = prev_j
    order.reverse()
    return order


def _nearest_neighbour(
    dist: Distances, depot: int, stops: Sequence[int], start: int | None = None
) -> list[int]:
    remaining = list(stops)
    order: list[int] = []
    here = depot
    if start is not None:
        remaining.remove(start)
        order.append(start)
        here = start
    while remaining:
        nxt = min(remaining, key=lambda k: (dist[here][k], k))
        remaining.remove(nxt)
        order.append(nxt)
        here = nxt
    return order


def _two_opt(dist: Rows, depot: int, order: list[int], final: int | None) -> list[int]:
    improved = True
    best = route_length(dist, depot, order, final)
    while improved:
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 1, len(order)):
                cand = order[:i] + order[i : j + 1][::-1] + order[j + 1 :]
                length = route_length(dist, depot, cand, final)
                if length < best - 1e-9:
                    order, best, improved = cand, length, True
    return order


def _or_opt(dist: Rows, depot: int, order: list[int], final: int | None) -> list[int]:
    improved = True
    best = route_length(dist, depot, order, final)
    while improved:
        improved = False
        for seg in (1, 2, 3):
            for i in range(len(order) - seg + 1):
                segment = order[i : i + seg]
                rest = order[:i] + order[i + seg :]
                for k in range(len(rest) + 1):
                    if k == i:
                        continue
                    for piece in (segment, segment[::-1]):
                        cand = rest[:k] + piece + rest[k:]
                        length = route_length(dist, depot, cand, final)
                        if length < best - 1e-9:
                            order, best, improved = cand, length, True
                            break
                    if improved:
                        break
                if improved:
                    break
            if improved:
                break
    return order


def heuristic(
    dist: Matrix | Rows,
    depot: int,
    stops: Sequence[int],
    final: int | None,
    *,
    restarts: int = RESTARTS,
) -> list[int]:
    rng = random.Random(SEED)  # noqa: S311 (deterministic search restarts, not security)
    rows: list[list[float]] = np.asarray(dist, dtype=np.float64).tolist()
    starts: list[list[int]] = [_nearest_neighbour(rows, depot, stops)]
    pool = list(stops)
    for _ in range(restarts):
        shuffled = pool[:]
        rng.shuffle(shuffled)
        starts.append(shuffled)
    best_order: list[int] = []
    best_len = float("inf")
    for seed_order in starts:
        order = seed_order
        while True:
            before = route_length(rows, depot, order, final)
            order = _or_opt(rows, depot, _two_opt(rows, depot, order, final), final)
            if route_length(rows, depot, order, final) >= before - 1e-9:
                break
        length = route_length(rows, depot, order, final)
        if length < best_len - 1e-9:
            best_order, best_len = order, length
    return best_order


def optimize(
    dist: Matrix,
    *,
    depot: int,
    stops: Sequence[int],
    final: int | None = None,
    exact_limit: int = EXACT_LIMIT,
) -> RouteResult:
    """Order ``stops``. ``dist`` is a square symmetric-or-not matrix indexed by node."""
    if len(set(stops)) != len(stops) or depot in stops or (final is not None and final in stops):
        raise ValueError("stops must be unique and exclude the depot and the final node")
    if len(stops) <= 1:
        order, method = list(stops), "trivial"
    elif len(stops) <= exact_limit:
        order, method = exact(dist, depot, stops, final), "exact_held_karp"
    else:
        order, method = heuristic(dist, depot, stops, final), "nn_2opt_oropt"
    rows = np.asarray(dist, dtype=np.float64).tolist()
    return RouteResult(
        order=order,
        length=route_length(rows, depot, order, final),
        method=method,
        legs=_legs(rows, depot, order, final),
    )
