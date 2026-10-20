"""Route ordering: exactness against brute force, determinism, geometry."""

from __future__ import annotations

import itertools
import math

import numpy as np
import pytest

from app.modules.route_planning import optimizer as opt


def euclid(points: list[tuple[float, float]]) -> np.ndarray:
    n = len(points)
    return np.array(
        [[math.dist(points[i], points[j]) for j in range(n)] for i in range(n)], dtype=np.float64
    )


def random_instance(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return euclid([(float(x), float(y)) for x, y in rng.uniform(0, 100, size=(n, 2))])


def brute_force(dist: np.ndarray, depot: int, stops: list[int], final: int | None) -> float:
    return min(opt.route_length(dist, depot, list(p), final) for p in itertools.permutations(stops))


@pytest.mark.parametrize("seed", range(6))
@pytest.mark.parametrize("with_final", [False, True])
def test_exact_matches_brute_force(seed: int, with_final: bool) -> None:
    dist = random_instance(8, seed)
    final = 7 if with_final else None
    stops = [1, 2, 3, 4, 5, 6]
    got = opt.optimize(dist, depot=0, stops=stops, final=final)
    assert got.method == "exact_held_karp"
    assert sorted(got.order) == stops
    assert got.length == pytest.approx(brute_force(dist, 0, stops, final))
    assert got.length == pytest.approx(sum(got.legs))


def test_asymmetric_distances_are_respected() -> None:
    dist = random_instance(6, 3)
    skew = dist.copy()
    skew[1, 2] *= 5  # leaving 1 towards 2 is expensive, the reverse is not
    got = opt.optimize(skew, depot=0, stops=[1, 2, 3, 4, 5])
    assert got.length == pytest.approx(brute_force(skew, 0, [1, 2, 3, 4, 5], None))


def test_heuristic_is_valid_deterministic_and_near_optimal() -> None:
    dist = random_instance(11, 5)
    stops = list(range(1, 10))
    final = 10
    exact = opt.optimize(dist, depot=0, stops=stops, final=final)
    h1 = opt.optimize(dist, depot=0, stops=stops, final=final, exact_limit=3)
    h2 = opt.optimize(dist, depot=0, stops=stops, final=final, exact_limit=3)
    assert h1.method == "nn_2opt_oropt" and h1.order == h2.order and h1.length == h2.length
    assert sorted(h1.order) == stops
    assert h1.length >= exact.length - 1e-9
    assert h1.length <= exact.length * 1.05  # 2-opt/Or-opt with restarts on 9 stops


def test_heuristic_never_worse_than_nearest_neighbour() -> None:
    dist = random_instance(30, 9)
    stops = list(range(1, 30))
    nn = opt.route_length(dist, 0, opt._nearest_neighbour(dist, 0, stops), None)
    got = opt.optimize(dist, depot=0, stops=stops)
    assert got.method == "nn_2opt_oropt" and got.length <= nn + 1e-9
    assert sorted(got.order) == stops


def test_trivial_and_invalid_inputs() -> None:
    dist = random_instance(4, 1)
    assert opt.optimize(dist, depot=0, stops=[]).order == []
    one = opt.optimize(dist, depot=0, stops=[2], final=3)
    assert one.order == [2] and one.method == "trivial"
    assert one.length == pytest.approx(dist[0, 2] + dist[2, 3] + dist[3, 0])
    for stops, final in (([1, 1], None), ([0, 1], None), ([1, 2], 2)):
        with pytest.raises(ValueError):
            opt.optimize(dist, depot=0, stops=stops, final=final)


def test_haversine_known_distances_and_symmetry() -> None:
    one_degree = math.radians(1) * opt.EARTH_RADIUS_M
    assert opt.haversine_m(0, 0, 1, 0) == pytest.approx(one_degree)
    assert opt.haversine_m(0, 0, 0, 1) == pytest.approx(one_degree)
    assert opt.haversine_m(17.385, 78.4867, 17.385, 78.4867) == 0.0
    a, b = (17.385, 78.4867), (17.4399, 78.4983)
    assert opt.haversine_m(*a, *b) == pytest.approx(opt.haversine_m(*b, *a))
    assert 6_000 < opt.haversine_m(*a, *b) < 6_300  # ~6.1 km between these two points
    matrix = opt.haversine_matrix([a, b, (17.40, 78.50)])
    assert np.allclose(matrix, matrix.T) and np.all(np.diag(matrix) == 0)
