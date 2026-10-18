"""Enumerations shared by more than one module.

Module-specific enumerations (statuses, types) live in that module's ``constants.py``.
"""

from __future__ import annotations

from enum import StrEnum


class QuantityUnit(StrEnum):
    """Units permitted wherever a quantity column carries an explicit unit column."""

    KILOGRAM = "kg"
    TONNE = "t"
    CUBIC_METRE = "m3"
    LITRE = "l"
    ITEM = "item"


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"
