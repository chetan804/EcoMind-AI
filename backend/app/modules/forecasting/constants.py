from __future__ import annotations

from enum import StrEnum


class ForecastGranularity(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
