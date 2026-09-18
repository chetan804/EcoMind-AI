from typing import Protocol, Sequence


class OptimizationUnavailable(RuntimeError):
    """Raised when a route optimization solver is not installed or configured."""


class RouteOptimizationAdapter(Protocol):
    def optimize(self, distance_matrix: Sequence[Sequence[int]]) -> list[int]:
        """Return stop indexes in optimized order."""
