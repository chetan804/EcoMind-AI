from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from app.integrations.routing.base import RoutingAdapter
from app.models.collection import WasteCollection


@dataclass(frozen=True)
class OrderedStop:
    collection: WasteCollection
    stop_order: int
    distance_from_previous_km: float


@dataclass(frozen=True)
class RoutePlan:
    stops: list[OrderedStop]
    total_distance_km: float
    estimated_duration_minutes: float


def haversine_distance_km(
    latitude_one: float,
    longitude_one: float,
    latitude_two: float,
    longitude_two: float,
) -> float:
    earth_radius_km = 6371.0
    latitude_delta = radians(latitude_two - latitude_one)
    longitude_delta = radians(longitude_two - longitude_one)
    value = (
        sin(latitude_delta / 2) ** 2
        + cos(radians(latitude_one))
        * cos(radians(latitude_two))
        * sin(longitude_delta / 2) ** 2
    )
    return 2 * earth_radius_km * asin(sqrt(value))


def optimize_collections(
    collections: list[WasteCollection],
    start_latitude: float | None = None,
    start_longitude: float | None = None,
    average_speed_kmh: float = 25.0,
    routing_adapter: RoutingAdapter | None = None,
) -> RoutePlan:
    pending = [
        collection
        for collection in collections
        if collection.report.latitude is not None
        and collection.report.longitude is not None
    ]
    if not pending:
        return RoutePlan([], 0.0, 0.0)

    current_latitude = start_latitude
    current_longitude = start_longitude
    ordered: list[OrderedStop] = []
    total_distance = 0.0

    while pending:
        if current_latitude is None or current_longitude is None:
            selected = pending[0]
            distance = 0.0
        else:
            selected, distance = min(
                (
                    (
                        collection,
                        haversine_distance_km(
                            current_latitude,
                            current_longitude,
                            collection.report.latitude,
                            collection.report.longitude,
                        ),
                    )
                    for collection in pending
                ),
                key=lambda item: item[1],
            )

        pending.remove(selected)
        ordered.append(
            OrderedStop(
                collection=selected,
                stop_order=len(ordered) + 1,
                distance_from_previous_km=distance,
            )
        )
        total_distance += distance
        current_latitude = selected.report.latitude
        current_longitude = selected.report.longitude

    estimated_duration = (
        total_distance / average_speed_kmh * 60
        if average_speed_kmh > 0
        else 0.0
    )

    if routing_adapter is not None and ordered:
        route_coordinates: list[tuple[float, float]] = []
        if start_latitude is not None and start_longitude is not None:
            route_coordinates.append((start_latitude, start_longitude))
        route_coordinates.extend(
            (stop.collection.report.latitude, stop.collection.report.longitude)
            for stop in ordered
        )
        legs = routing_adapter.route(route_coordinates)
        if len(legs) == len(ordered):
            ordered = [
                OrderedStop(
                    collection=stop.collection,
                    stop_order=stop.stop_order,
                    distance_from_previous_km=leg.distance_km,
                )
                for stop, leg in zip(ordered, legs)
            ]
            total_distance = sum(leg.distance_km for leg in legs)
            estimated_duration = sum(leg.duration_minutes for leg in legs)
        elif start_latitude is None and len(legs) == len(ordered) - 1:
            first_stop = ordered[0]
            ordered = [first_stop] + [
                OrderedStop(
                    collection=stop.collection,
                    stop_order=stop.stop_order,
                    distance_from_previous_km=leg.distance_km,
                )
                for stop, leg in zip(ordered[1:], legs)
            ]
            total_distance = sum(leg.distance_km for leg in legs)
            estimated_duration = sum(leg.duration_minutes for leg in legs)

    return RoutePlan(ordered, total_distance, estimated_duration)
