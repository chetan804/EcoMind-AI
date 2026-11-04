"""Size profiles. ``rows`` are rough totals across every table (see README for measured counts)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    days: int  # days of history ending on the anchor date
    tasks_per_day: float  # weekday average; weekends are lighter
    citizens: int
    collectors: int
    operators_per_site: int
    managers: int
    drop_offs: int
    pings_per_leg: int  # simulated GPS points between two stops
    approx_rows: str


PROFILES: dict[str, Profile] = {
    # Used by the automated tests: a couple of thousand rows, a few seconds.
    "test": Profile("test", 70, 7, 40, 6, 1, 2, 3, 1, "about 9,000"),
    # Enough weeks of history (>= 26) for the forecaster; a few tens of thousands of rows.
    "development": Profile("development", 210, 10, 400, 18, 2, 4, 6, 2, "20,000-50,000"),
    "integration": Profile("integration", 270, 45, 4_000, 60, 2, 6, 12, 2, "100,000-300,000"),
    "large": Profile("large", 365, 230, 40_000, 300, 3, 10, 12, 1, "1-2 million"),
    "stress": Profile("stress", 730, 420, 150_000, 800, 3, 16, 12, 0, "5 million or more"),
}
