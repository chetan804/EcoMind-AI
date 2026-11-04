"""Representative Hyderabad localities used to place synthetic records.

IMPORTANT: coordinates are APPROXIMATE locality centres written from general knowledge. They are
not surveyed points and they are not official GHMC wards or circles. The population weights are
invented to give a believable spread (dense areas report more); they are not census figures.
Everything derived from this file (zones, facilities, addresses) is synthetic and labelled so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Locality:
    name: str
    lat: float
    lon: float
    zone_type: str  # a value of the zones.zone_type check constraint
    weight: float  # relative share of reports (invented)


LOCALITIES: tuple[Locality, ...] = (
    Locality("Uppal", 17.4058, 78.5591, "mixed_use", 1.3),
    Locality("Habsiguda", 17.4146, 78.5410, "residential", 1.0),
    Locality("Tarnaka", 17.4286, 78.5390, "mixed_use", 1.0),
    Locality("Nacharam", 17.4295, 78.5700, "industrial", 0.9),
    Locality("Mallapur", 17.4450, 78.5750, "industrial", 0.8),
    Locality("Boduppal", 17.4160, 78.5990, "residential", 1.1),
    Locality("Peerzadiguda", 17.4117, 78.6139, "residential", 0.8),
    Locality("LB Nagar", 17.3457, 78.5522, "mixed_use", 1.4),
    Locality("Dilsukhnagar", 17.3688, 78.5247, "commercial", 1.6),
    Locality("Kothapet", 17.3680, 78.5400, "residential", 1.0),
    Locality("Nagole", 17.3720, 78.5590, "residential", 1.1),
    Locality("Hayathnagar", 17.3270, 78.6000, "residential", 0.8),
    Locality("Secunderabad", 17.4399, 78.4983, "commercial", 1.6),
    Locality("Malkajgiri", 17.4560, 78.5270, "residential", 1.2),
    Locality("Kapra", 17.4780, 78.5650, "residential", 0.9),
    Locality("ECIL", 17.4700, 78.5700, "industrial", 0.8),
    Locality("Begumpet", 17.4440, 78.4670, "commercial", 1.0),
    Locality("Ameerpet", 17.4375, 78.4483, "commercial", 1.5),
    Locality("Kukatpally", 17.4849, 78.4138, "mixed_use", 1.9),
    Locality("Miyapur", 17.4967, 78.3590, "residential", 1.1),
    Locality("Gachibowli", 17.4401, 78.3489, "institutional", 1.2),
    Locality("Kondapur", 17.4600, 78.3570, "mixed_use", 1.2),
    Locality("Madhapur", 17.4486, 78.3908, "commercial", 1.4),
    Locality("HITEC City", 17.4435, 78.3772, "commercial", 1.1),
    Locality("Jubilee Hills", 17.4326, 78.4071, "residential", 0.9),
    Locality("Banjara Hills", 17.4126, 78.4482, "residential", 1.0),
    Locality("Mehdipatnam", 17.3950, 78.4400, "mixed_use", 1.4),
    Locality("Charminar", 17.3616, 78.4747, "mixed_use", 1.5),
    Locality("Malakpet", 17.3750, 78.5000, "mixed_use", 1.1),
    Locality("Amberpet", 17.3990, 78.5180, "residential", 0.9),
    Locality("Musheerabad", 17.4100, 78.4900, "residential", 1.0),
)

# (code suffix, name, locality it sits in). Depots park the fleet; processing centres recover
# material; transfer stations consolidate loads. Sites are invented.
DEPOTS = (
    ("DEP-01", "Uppal Depot", "Uppal"),
    ("DEP-02", "Secunderabad Depot", "Secunderabad"),
    ("DEP-03", "Kukatpally Depot", "Kukatpally"),
    ("DEP-04", "Gachibowli Depot", "Gachibowli"),
    ("DEP-05", "Mehdipatnam Depot", "Mehdipatnam"),
    ("DEP-06", "LB Nagar Depot", "LB Nagar"),
)
PROCESSING = (
    ("PC-01", "Kapra Recovery Centre", "Kapra"),
    ("PC-02", "Miyapur Recovery Centre", "Miyapur"),
    ("PC-03", "Hayathnagar Recovery Centre", "Hayathnagar"),
    ("PC-04", "Malkajgiri Recovery Centre", "Malkajgiri"),
)
TRANSFER = (
    ("TS-01", "Nacharam Transfer Station", "Nacharam"),
    ("TS-02", "Begumpet Transfer Station", "Begumpet"),
    ("TS-03", "Madhapur Transfer Station", "Madhapur"),
    ("TS-04", "Malakpet Transfer Station", "Malakpet"),
    ("TS-05", "Boduppal Transfer Station", "Boduppal"),
)
DROP_OFF_LOCALITIES = (
    "Habsiguda", "Tarnaka", "Dilsukhnagar", "Ameerpet", "Kondapur", "HITEC City",
    "Banjara Hills", "Charminar", "Nagole", "Musheerabad", "Jubilee Hills", "Amberpet",
)  # fmt: skip

BY_NAME = {loc.name: loc for loc in LOCALITIES}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360
