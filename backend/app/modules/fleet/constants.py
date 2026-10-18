from __future__ import annotations

from enum import StrEnum


class VehicleType(StrEnum):
    COMPACTOR_TRUCK = "compactor_truck"
    TIPPER_TRUCK = "tipper_truck"
    VAN = "van"
    CARGO_BIKE = "cargo_bike"
    OTHER = "other"


class VehicleStatus(StrEnum):
    AVAILABLE = "available"
    IN_SERVICE = "in_service"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"
