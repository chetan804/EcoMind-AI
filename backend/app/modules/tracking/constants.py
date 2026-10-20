from __future__ import annotations

from enum import StrEnum


class LocationSource(StrEnum):
    """Where an event came from. The source decides how the position may be presented."""

    GPS_DEVICE = "gps_device"  # an on-board tracker posting through an authorised account
    MOBILE_CLIENT = "mobile_client"  # the assigned collector's phone
    IMPORTED = "imported"  # a manager importing a past track; always shown as historical
    SIMULATOR = "simulator"  # demonstration data; never mixed with the real sources


REPORTABLE_SOURCES = frozenset({LocationSource.GPS_DEVICE, LocationSource.MOBILE_CLIENT})


class LocationQuality(StrEnum):
    ACCEPTED = "accepted"  # newer than every earlier event of the vehicle and source group
    OUT_OF_ORDER = "out_of_order"  # stored, but an event with a later timestamp already existed


class TrackingStatus(StrEnum):
    """How a displayed position must be labelled. Derived at read time, never stored."""

    LIVE = "live"  # real source, received within the live window
    DELAYED = "delayed"  # real source, older than the live window but not stale
    STALE = "stale"  # real source, older than the stale threshold
    HISTORICAL = "historical"  # imported track
    SIMULATED = "simulated"  # simulator source
    UNAVAILABLE = "unavailable"  # the vehicle has no recorded position at all
