"""Vehicle-routing optimisation (OR-Tools CVRP-TW).

Responsibility: *which stops, in what sequence* — the combinatorial problem.
Road geometry (real streets) is a separate concern handled by
``app/routing/roads.py``; here distances are haversine-based cost estimates,
which is exactly what OR-Tools needs to optimise sequencing.

Constraints supported:
- per-vehicle capacity (kg)
- per-stop service time and optional time windows
- priority weighting (high-priority stops get larger drop penalties)
- optional stop dropping (unservicable demand is reported, not silently lost)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.core.gis import haversine_km
from app.core.logging import get_logger

log = get_logger("routing")

SOLVE_TIME_LIMIT_S = 5.0


@dataclass(slots=True)
class StopSpec:
    key: str
    lat: float
    lng: float
    demand_kg: float = 0.0
    service_min: float = 5.0
    priority: int = 0  # 0 normal, >0 elevated (drop penalty scaled)
    time_window_min: tuple[float, float] | None = None


@dataclass(slots=True)
class VehicleSpec:
    key: str
    capacity_kg: float


@dataclass(slots=True)
class VehiclePlan:
    vehicle_key: str
    stop_keys: list[str] = field(default_factory=list)
    distance_km: float = 0.0
    duration_min: float = 0.0
    load_kg: float = 0.0


@dataclass(slots=True)
class OptimisationResult:
    plans: list[VehiclePlan] = field(default_factory=list)
    unassigned: list[str] = field(default_factory=list)
    total_distance_km: float = 0.0
    solver_status: str = "not_run"
    solve_ms: int = 0
    solver: str = "ortools-cvrp"


def _distance_matrix(depot: tuple[float, float], stops: list[StopSpec]) -> list[list[int]]:
    """Haversine distance matrix in integer metres (OR-Tools needs ints)."""
    coords = [(depot[0], depot[1])] + [(s.lat, s.lng) for s in stops]
    n = len(coords)
    matrix = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = int(haversine_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1]) * 1000)
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def solve(
    *,
    depot: tuple[float, float],
    stops: list[StopSpec],
    vehicles: list[VehicleSpec],
    avg_speed_kmh: float = 22.0,
) -> OptimisationResult:
    if not stops or not vehicles:
        return OptimisationResult(solver_status="no_input")
    matrix = _distance_matrix(depot, stops)
    n_stops = len(stops)
    n_vehicles = len(vehicles)
    depot_index = 0  # single depot: every route starts and ends at node 0

    manager = pywrapcp.RoutingIndexManager(
        n_stops + 1, n_vehicles, [depot_index] * n_vehicles, [depot_index] * n_vehicles
    )
    routing = pywrapcp.RoutingModel(manager)

    def distance_cb(from_index, to_index):
        return matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit_cb = routing.RegisterTransitCallback(distance_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_cb)

    # Capacity dimension (kg)
    demands = [0] + [int(max(0, s.demand_kg)) for s in stops]

    def demand_cb(from_index):
        return demands[manager.IndexToNode(from_index)]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index, 0, [int(max(0, v.capacity_kg)) for v in vehicles], True, "Capacity"
    )

    # Time dimension (service + travel), used for time windows
    speeds_m_per_min = avg_speed_kmh * 1000 / 60

    def time_cb(from_index, to_index):
        travel_min = matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)] / speeds_m_per_min
        service = stops[manager.IndexToNode(from_index) - 1].service_min if manager.IndexToNode(from_index) > 0 else 0.0
        return int(travel_min + service)

    time_cb_index = routing.RegisterTransitCallback(time_cb)
    horizon = 24 * 60
    routing.AddDimension(time_cb_index, 30, horizon, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    for stop_idx, spec in enumerate(stops, start=1):
        index = manager.NodeToIndex(stop_idx)
        if spec.time_window_min is not None:
            time_dim.CumulVar(index).SetRange(int(spec.time_window_min[0]), int(spec.time_window_min[1]))

    # Drop penalties: any stop may be dropped under capacity pressure, but
    # higher priority stops cost (much) more to drop, and nothing is silent.
    base_penalty = 100_000
    for stop_idx, spec in enumerate(stops, start=1):
        index = manager.NodeToIndex(stop_idx)
        routing.AddDisjunction([index], base_penalty * (1 + spec.priority * 4))

    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    search.time_limit.FromMilliseconds(int(SOLVE_TIME_LIMIT_S * 1000))

    started = time.perf_counter()
    solution = routing.SolveWithParameters(search)
    solve_ms = int((time.perf_counter() - started) * 1000)

    if solution is None:
        return OptimisationResult(
            unassigned=[s.key for s in stops], solver_status="no_solution", solve_ms=solve_ms
        )

    plans: list[VehiclePlan] = []
    unassigned = []
    total_distance = 0.0

    for vehicle_idx, vspec in enumerate(vehicles):
        plan = VehiclePlan(vehicle_key=vspec.key)
        index = routing.Start(vehicle_idx)
        route_distance = 0
        load = 0
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                spec = stops[node - 1]
                plan.stop_keys.append(spec.key)
                load += demands[node]
            prev = index
            index = solution.Value(routing.NextVar(index))
            route_distance += matrix[manager.IndexToNode(prev)][manager.IndexToNode(index)]
        plan.distance_km = route_distance / 1000.0
        service_total = sum(s.service_min for s in stops if s.key in set(plan.stop_keys))
        plan.duration_min = route_distance / 1000.0 / avg_speed_kmh * 60 + service_total
        plan.load_kg = float(load)
        plans.append(plan)
        total_distance += plan.distance_km

    planned_keys = {k for p in plans for k in p.stop_keys}
    unassigned = [s.key for s in stops if s.key not in planned_keys]

    return OptimisationResult(
        plans=plans,
        unassigned=unassigned,
        total_distance_km=total_distance,
        solver_status="optimal_found" if routing.status() == 1 else f"status_{routing.status()}",
        solve_ms=solve_ms,
    )
