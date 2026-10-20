"""Loaders and audit for the public municipal-waste time series (git-ignored raw data).

Source: https://github.com/UCloudMl/solid-waste-prediction (MIT; data from municipal
authorities, see docs/ml/dataset-research/). The loaders never repair data silently: every
exclusion and fill is counted and reported by ``audit``.
"""

from __future__ import annotations

import csv
import datetime as dt
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

REPO = Path(__file__).resolve().parents[2]

# Pinned source (git-ignored clone; fetched with `git clone` + `git checkout <commit>`).
SOURCE = {
    "url": "https://github.com/UCloudMl/solid-waste-prediction",
    "commit": "6ff6b1a073e7acbe7725150119a74c5f2fba26d2",
    "licence_note": (
        "Repository licence: MIT. The repository does not state the licence of the underlying "
        "municipal/open-data records, which is therefore unverified; cite Mudannayake et al., "
        "'Exploring Machine Learning and Deep Learning Approaches for Multi-Step Forecasting "
        "in Municipal Solid Waste Generation', IEEE Access, 2022."
    ),
}
MSW = REPO / "datasets" / "external" / "msw-src" / "dataset"

# series key -> (file, date format, human name, country)
SERIES: dict[str, tuple[str, str, str, str]] = {
    "boralesgamuwa": (
        "boralasgamuwa_uc_2012-2018.csv",
        "%Y-%m-%d",
        "Boralesgamuwa UC",
        "Sri Lanka",
    ),
    "dehiwala": ("dehiwala_mc_2012-2018.csv", "%Y-%m-%d", "Dehiwala MC", "Sri Lanka"),
    "homagama": ("homagama_ps_2012-2018.csv", "%Y-%m-%d", "Homagama PS", "Sri Lanka"),
    "austin": (
        "open_source_austin_daily_waste_2003_jan_2021_jul.csv",
        "%Y-%m-%d",
        "Austin (TX)",
        "USA",
    ),
    "ballarat": (
        "open_source_ballarat_daily_waste_2000_jul_2015_mar.csv",
        "%Y-%m-%d",
        "Ballarat",
        "Australia",
    ),
}
# Moratuwa is deliberately NOT usable: see docs/ml/dataset-research/ingestion/timeseries.md.
EXCLUDED = {
    "moratuwa": "ticket_date appears day/month-swapped for days <= 12 (series ends 2018-12-11)",
    "kerawalapitiya": "per-vehicle tickets; used for anomaly experiments only, not forecasting",
}


@dataclass
class DailyAudit:
    rows: int = 0
    unparseable: int = 0
    non_positive: int = 0
    duplicates_days: int = 0
    days: int = 0
    first: dt.date | None = None
    last: dt.date | None = None
    coverage: float = 0.0
    weekday_presence: list[float] = field(default_factory=list)


def verify_pinned_commit() -> None:
    """Refuse to use a checkout that is not the commit the documentation describes."""
    import subprocess

    head = subprocess.run(  # noqa: S603 (fixed argument list, no shell)
        ["git", "-C", str(MSW.parent), "rev-parse", "HEAD"],  # noqa: S607
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if head != SOURCE["commit"]:
        raise RuntimeError(f"msw-src is at {head}, expected pinned commit {SOURCE['commit']}")


def load_daily(key: str) -> tuple[dict[dt.date, float], DailyAudit]:
    """Total net weight (kg) per calendar day; days with no ticket are ABSENT, never zero."""
    file, fmt, _, _ = SERIES[key]
    totals: dict[dt.date, float] = defaultdict(float)
    audit = DailyAudit()
    with (MSW / file).open(newline="") as handle:
        for row in csv.DictReader(handle):
            audit.rows += 1
            try:
                day = dt.datetime.strptime(row["ticket_date"].strip(), fmt).date()
                weight = float(row["net_weight_kg"])
            except (ValueError, KeyError):
                audit.unparseable += 1
                continue
            if not math.isfinite(weight) or weight <= 0:
                audit.non_positive += 1
                continue
            if day in totals:
                audit.duplicates_days += 1  # several tickets on a day are summed (expected)
            totals[day] += weight
    days = sorted(totals)
    audit.days, audit.first, audit.last = len(days), days[0], days[-1]
    span = (days[-1] - days[0]).days + 1
    audit.coverage = len(days) / span
    counts = defaultdict(int)
    for day in days:
        counts[day.weekday()] += 1
    weeks = span / 7
    audit.weekday_presence = [round(counts[i] / weeks, 3) for i in range(7)]
    return dict(totals), audit


@dataclass
class WeeklySeries:
    key: str
    week_start: list[dt.date]
    values: NDArray[np.float64]  # complete weeks: total kg; incomplete weeks: linearly interpolated
    complete: NDArray[np.bool_]
    operating_weekdays: list[int]
    rule: str

    @property
    def n_filled(self) -> int:
        return int((~self.complete).sum())


def weekly(daily: dict[dt.date, float], key: str = "") -> WeeklySeries:
    """Monday-based weekly totals.

    A weekday is an *operating* day when it has data in >= 50% of weeks. A week is complete when
    it has data on >= 80% of the operating weekdays (rounded up); otherwise it is marked
    incomplete (interpolated for model fitting only, never scored).
    """
    days = sorted(daily)
    start = days[0] - dt.timedelta(days=days[0].weekday())
    end = days[-1] - dt.timedelta(days=days[-1].weekday())
    n_weeks = (end - start).days // 7 + 1
    sums = np.zeros(n_weeks)
    seen = np.zeros((n_weeks, 7), dtype=bool)
    for day, kg in daily.items():
        w = (day - start).days // 7
        sums[w] += kg
        seen[w, day.weekday()] = True
    presence = seen[1:-1].mean(axis=0) if n_weeks > 2 else seen.mean(axis=0)
    operating = [i for i in range(7) if presence[i] >= 0.5]
    need = math.ceil(0.8 * len(operating))
    complete = seen[:, operating].sum(axis=1) >= need
    complete[0] = complete[-1] = False  # boundary weeks are partial by construction
    values = sums.copy()
    values[~complete] = np.nan
    good = np.flatnonzero(complete)
    values = np.interp(np.arange(n_weeks), good, values[good])
    # trim leading/trailing incomplete weeks (interpolation there would be extrapolation)
    lo, hi = int(good[0]), int(good[-1])
    weeks = [start + dt.timedelta(days=7 * i) for i in range(n_weeks)]
    return WeeklySeries(
        key,
        weeks[lo : hi + 1],
        values[lo : hi + 1],
        complete[lo : hi + 1],
        operating,
        f"operating weekdays {operating}; week complete if >= {need} of {len(operating)} present",
    )
