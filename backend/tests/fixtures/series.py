"""Seed helpers for forecasting/anomaly tests. Synthetic data lives ONLY in tests."""

from __future__ import annotations

import datetime as dt
import decimal
import math
import uuid

import numpy as np
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.common.enums import QuantityUnit
from app.modules.collection.constants import CollectionEventType, CollectionTaskStatus
from app.modules.collection.models import CollectionEvent, CollectionTask
from app.modules.forecasting import repository
from app.modules.forecasting.constants import ForecastGranularity


def monday_of(day: dt.date) -> dt.date:
    return day - dt.timedelta(days=day.weekday())


def seasonal_values(
    n: int, *, base: float = 20_000.0, amp: float = 4_000.0, noise: float = 300.0, seed: int = 7
) -> list[float]:
    rng = np.random.default_rng(seed)
    return [
        max(base + amp * math.sin(2 * math.pi * i / 52) + float(rng.normal(0, noise)), 1.0)
        for i in range(n)
    ]


def seed_reference(
    engine: Engine,
    key: str,
    values: list[float],
    *,
    interpolated: set[int] | None = None,
    start: dt.date = dt.date(2015, 1, 5),
) -> list[dt.date]:
    weeks = [start + dt.timedelta(days=7 * i) for i in range(len(values))]
    with Session(engine) as db:
        repository.replace_reference_series(
            db,
            fields={
                "key": key,
                "name": f"Test series {key}",
                "country": "Testland",
                "unit": QuantityUnit.KILOGRAM,
                "granularity": ForecastGranularity.WEEK,
                "source_url": "https://example.org/test-series",
                "source_commit": "0" * 40,
                "licence_note": "test fixture",
                "processing_note": "synthetic test fixture",
                "first_period": weeks[0],
                "last_period": weeks[-1],
                "point_count": len(values),
            },
            points=[
                (w, decimal.Decimal(repr(round(v, 3))), i in (interpolated or set()))
                for i, (w, v) in enumerate(zip(range(len(values)), values, strict=True))
                for w in [weeks[i]]
            ],
        )
        db.commit()
    return weeks


def seed_platform_weeks(
    engine: Engine, user_id: uuid.UUID, weekly_kg: dict[dt.date, float]
) -> None:
    """One completed-looking task with one ``collected`` event per week (Wednesday)."""
    with Session(engine) as db:
        task = CollectionTask(
            title="seed",
            status=CollectionTaskStatus.COMPLETED,
            created_by_id=user_id,
        )
        db.add(task)
        db.flush()
        for week, kg in weekly_kg.items():
            db.add(
                CollectionEvent(
                    collection_task_id=task.id,
                    event_type=CollectionEventType.COLLECTED,
                    occurred_at=dt.datetime.combine(
                        week + dt.timedelta(days=2), dt.time(10), dt.UTC
                    ),
                    recorded_by_id=user_id,
                    collected_weight_kg=decimal.Decimal(repr(kg)),
                )
            )
        db.commit()


def count(engine: Engine, query: str, **params: object) -> int:
    with engine.connect() as conn:
        return int(conn.execute(text(query), params).scalar_one())
