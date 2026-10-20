"""Analytics: figures must equal what is stored, and be empty (not invented) when nothing is."""

from __future__ import annotations

import datetime as dt
import decimal
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.modules.collection.constants import CollectionTaskStatus
from app.modules.collection.models import CollectionTask
from tests.fixtures.api import ClientFactory, bearer, create_user, login
from tests.fixtures.series import monday_of, seed_platform_weeks

BASE = "/api/v1/analytics"
INCIDENTS = "/api/v1/community-incidents"


class Env:
    def __init__(self, client: TestClient, engine: Engine) -> None:
        self.client, self.engine = client, engine
        self.ids: dict[str, uuid.UUID] = {}
        self.h: dict[str, dict[str, str]] = {}
        for role in ("citizen", "collector", "facility_operator", "manager"):
            email = f"{role}@example.org"
            self.ids[role] = create_user(engine, email=email, roles=(role,))
            self.h[role] = bearer(login(client, email)["access_token"])

    def get(self, path: str, who: str = "manager", **params: Any) -> Any:
        return self.client.get(BASE + path, params=params, headers=self.h[who])


@pytest.fixture
def env(make_client: ClientFactory, db_engine: Engine) -> Env:
    return Env(make_client(), db_engine)


def counts(items: list[dict[str, Any]]) -> dict[str, int]:
    return {i["key"]: i["count"] for i in items}


def test_permissions(env: Env) -> None:
    for path in ("/overview", "/weekly-trend"):
        assert env.client.get(BASE + path).status_code == 401
        for role in ("citizen", "collector", "facility_operator"):
            assert env.get(path, role).status_code == 403, (path, role)
        assert env.get(path).status_code == 200


def test_empty_platform_reports_zeros_not_invented_numbers(env: Env) -> None:
    body = env.get("/overview").json()
    assert body["reports"]["total"] == 0
    assert counts(body["reports"]["by_status"]) == {
        "submitted": 0,
        "under_review": 0,
        "verified": 0,
        "rejected": 0,
        "closed": 0,
    }
    assert body["collection"]["tasks_total"] == 0
    assert decimal.Decimal(body["collection"]["collected_weight_kg_total"]) == 0
    assert body["recovery"]["recovery_rate"] is None
    assert body["incidents"] == {"total": 0, "open_incidents": 0, "unassigned_open": 0}
    assert body["anomalies"] == {"open_alerts": 0, "critical_open": 0}
    assert body["rewards"]["net_points"] == 0
    assert "coefficient" in body["basis"]


def test_collected_weight_and_weekly_trend_equal_stored_events(env: Env) -> None:
    this_monday = monday_of(dt.datetime.now(dt.UTC).date())
    seed_platform_weeks(
        env.engine,
        env.ids["manager"],
        {
            this_monday - dt.timedelta(weeks=3): 100.0,
            this_monday - dt.timedelta(weeks=2): 200.5,
            this_monday - dt.timedelta(weeks=1): 50.0,
        },
    )
    overview = env.get("/overview", window_days=365).json()
    assert decimal.Decimal(overview["collection"]["collected_weight_kg_total"]) == decimal.Decimal(
        "350.5"
    )
    assert decimal.Decimal(
        overview["collection"]["collected_weight_kg_in_window"]
    ) == decimal.Decimal("350.5")
    assert overview["collection"]["completed_in_window"] == 1  # the seed uses one task

    # a one-day window sees none of the old events, while the total is unchanged
    narrow = env.get("/overview", window_days=1).json()
    assert decimal.Decimal(narrow["collection"]["collected_weight_kg_in_window"]) == 0
    assert decimal.Decimal(narrow["collection"]["collected_weight_kg_total"]) == decimal.Decimal(
        "350.5"
    )

    trend = env.get("/weekly-trend", weeks=4).json()
    assert [p["week_start"] for p in trend["points"]] == [
        (this_monday - dt.timedelta(weeks=n)).isoformat() for n in (3, 2, 1, 0)
    ]
    assert [decimal.Decimal(p["collected_weight_kg"]) for p in trend["points"]] == [
        decimal.Decimal("100"),
        decimal.Decimal("200.5"),
        decimal.Decimal("50"),
        decimal.Decimal("0"),
    ]
    assert [p["tasks_completed"] for p in trend["points"]] == [1, 1, 1, 0]


def test_open_and_overdue_tasks_are_counted_from_stored_state(env: Env) -> None:
    now = dt.datetime.now(dt.UTC)
    with Session(env.engine) as db:
        for title, status, due in (
            ("late open", CollectionTaskStatus.PENDING, now - dt.timedelta(days=1)),
            ("late assigned", CollectionTaskStatus.ASSIGNED, now - dt.timedelta(hours=1)),
            ("future", CollectionTaskStatus.PENDING, now + dt.timedelta(days=1)),
            ("late but done", CollectionTaskStatus.COMPLETED, now - dt.timedelta(days=2)),
            ("no due date", CollectionTaskStatus.PENDING, None),
        ):
            db.add(
                CollectionTask(
                    title=title, status=status, due_at=due, created_by_id=env.ids["manager"]
                )
            )
        db.commit()
    c = env.get("/overview").json()["collection"]
    assert c["tasks_total"] == 5
    assert c["open_tasks"] == 4
    assert c["overdue_tasks"] == 2
    assert counts(c["by_status"])["completed"] == 1


def test_incident_counts_follow_the_triage_lifecycle(env: Env) -> None:
    created = env.client.post(
        INCIDENTS,
        json={
            "incident_type": "overflowing_bin",
            "title": "Bin overflowing",
            "latitude": "17.385",
            "longitude": "78.486",
        },
        headers=env.h["citizen"],
    )
    assert created.status_code == 201
    assert env.get("/overview").json()["incidents"] == {
        "total": 1,
        "open_incidents": 1,
        "unassigned_open": 1,
    }
    moved = env.client.post(
        f"{INCIDENTS}/{created.json()['id']}/status",
        json={"status": "dismissed", "notes": "Duplicate of an earlier report"},
        headers=env.h["manager"],
    )
    assert moved.status_code == 200
    assert env.get("/overview").json()["incidents"] == {
        "total": 1,
        "open_incidents": 0,
        "unassigned_open": 0,
    }


@pytest.mark.parametrize(
    ("path", "params"),
    [
        ("/overview", {"window_days": 0}),
        ("/overview", {"window_days": 366}),
        ("/weekly-trend", {"weeks": 0}),
        ("/weekly-trend", {"weeks": 105}),
    ],
)
def test_parameter_bounds(env: Env, path: str, params: dict[str, int]) -> None:
    response = env.client.get(BASE + path, params=params, headers=env.h["manager"])
    assert response.status_code == 422
