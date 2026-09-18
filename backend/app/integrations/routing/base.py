from dataclasses import dataclass
from typing import Protocol, Sequence


class RoutingUnavailable(RuntimeError):
    """Raised when a configured routing provider cannot answer a request."""


@dataclass(frozen=True)
class RouteLeg:
    distance_km: float
    duration_minutes: float
    geometry: str | None = None


class RoutingAdapter(Protocol):
    def route(
        self,
        coordinates: Sequence[tuple[float, float]],
    ) -> list[RouteLeg]:
        """Return road-network legs between consecutive coordinates."""
