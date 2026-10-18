from __future__ import annotations

from enum import StrEnum


class DisposalMethod(StrEnum):
    RECYCLE = "recycle"
    COMPOST = "compost"
    REUSE = "reuse"
    LANDFILL = "landfill"
    HAZARDOUS_DROP_OFF = "hazardous_drop_off"
    E_WASTE_DROP_OFF = "e_waste_drop_off"
    SPECIAL_COLLECTION = "special_collection"
