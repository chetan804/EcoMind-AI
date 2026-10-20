from __future__ import annotations

from enum import StrEnum


class FacilityType(StrEnum):
    PROCESSING_CENTER = "processing_center"
    DEPOT = "depot"
    TRANSFER_STATION = "transfer_station"
    DROP_OFF_POINT = "drop_off_point"


class FacilityStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
