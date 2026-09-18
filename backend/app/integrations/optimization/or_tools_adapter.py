from collections.abc import Sequence

from app.integrations.optimization.base import OptimizationUnavailable


class ORToolsAdapter:
    def optimize(self, distance_matrix: Sequence[Sequence[int]]) -> list[int]:
        try:
            from ortools.constraint_solver import pywrapcp, routing_enums_pb2
        except ImportError as exc:
            raise OptimizationUnavailable("OR-Tools support requires ortools") from exc

        size = len(distance_matrix)
        if size == 0:
            return []
        manager = pywrapcp.RoutingIndexManager(size, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index: int, to_index: int) -> int:
            return int(distance_matrix[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)])

        callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(callback_index)
        parameters = pywrapcp.DefaultRoutingSearchParameters()
        parameters.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        solution = routing.SolveWithParameters(parameters)
        if solution is None:
            raise OptimizationUnavailable("OR-Tools could not find a route")

        order: list[int] = []
        index = routing.Start(0)
        while not routing.IsEnd(index):
            order.append(manager.IndexToNode(index))
            index = solution.Value(routing.NextVar(index))
        return order
