"""Shared setup for the material-chain API tests (recovery, passports, rewards)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.fixtures.api import ClientFactory, bearer, create_user, login

ROLES = ("citizen", "collector", "facility_operator", "manager", "administrator")


@dataclass
class Chain:
    client: TestClient
    engine: Engine
    ids: dict[str, uuid.UUID]
    h: dict[str, dict[str, str]]
    _facilities: dict[str, str] = field(default_factory=dict)

    def category(self, code: str = "plastic") -> str:
        page = self.client.get(
            "/api/v1/sorting-guide/categories", params={"page_size": 100}, headers=self.h["citizen"]
        )
        return str({c["code"]: c["id"] for c in page.json()["items"]}[code])

    def facility(self, code: str = "PLANT1", **extra: Any) -> str:
        if code in self._facilities:
            return self._facilities[code]
        wire_code = code if len(code) >= 2 else f"FAC-{code}"  # the API requires 2+ characters
        body = {
            "code": wire_code,
            "name": f"Plant {code}",
            "facility_type": "processing_center",
            **extra,
        }
        response = self.client.post("/api/v1/facilities", json=body, headers=self.h["manager"])
        assert response.status_code == 201, response.text
        self._facilities[code] = str(response.json()["id"])
        return self._facilities[code]

    def completed_task(self, kg: str = "40", *, report_id: str | None = None) -> str:
        """A task the collector has driven through to ``completed``."""
        base = "/api/v1/collection/tasks"
        body: dict[str, Any] = {"title": "Kerbside pickup", "address_text": "12 Main Street"}
        if report_id:
            body = {"waste_report_id": report_id}
        task = self.client.post(base, json=body, headers=self.h["manager"])
        assert task.status_code == 201, task.text
        task_id = task.json()["id"]
        steps: tuple[tuple[str, str, dict[str, Any]], ...] = (
            ("assign", "manager", {"assignee_id": str(self.ids["collector"])}),
            ("start", "collector", {}),
            ("complete", "collector", {"collected_weight_kg": kg}),
        )
        for step, who, payload in steps:
            r = self.client.post(f"{base}/{task_id}/{step}", json=payload, headers=self.h[who])
            assert r.status_code == 200, (step, r.text)
        return str(task_id)


@pytest.fixture
def chain(make_client: ClientFactory, db_engine: Engine) -> Chain:
    client = make_client()
    ids: dict[str, uuid.UUID] = {}
    heads: dict[str, dict[str, str]] = {}
    for role in ROLES:
        email = f"{role.replace('_', '')}@example.org"
        ids[role] = create_user(db_engine, email=email, roles=(role,))
        heads[role] = bearer(login(client, email)["access_token"])
    return Chain(client, db_engine, ids, heads)
