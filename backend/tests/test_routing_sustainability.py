"""Routing optimisation + sustainability engine tests."""

from __future__ import annotations

import uuid
from datetime import date

from conftest import api, create_point, make_org_with_admin


async def _make_vehicle(client, token, org_id, code, capacity_kg=5000):
    r = await api(
        client, "POST", "/api/v1/fleet/vehicles", token, org_id,
        json={"code": code, "vehicle_type": "compactor_truck", "fuel_type": "diesel",
              "capacity_kg": capacity_kg, "depot_lat": 12.94, "depot_lng": 77.60},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_route_generation_assigns_all_points_with_geometry(client):
    org, admin_token = await make_org_with_admin(client)
    import random

    random.seed(42)
    points = []
    for _ in range(12):
        lat = 12.94 + random.uniform(-0.02, 0.02)
        lng = 77.60 + random.uniform(-0.02, 0.02)
        points.append(await create_point(client, admin_token, org["id"], lat, lng))
    vehicle = await _make_vehicle(client, admin_token, org["id"], "RV-1")

    r = await api(
        client, "POST", "/api/v1/routes/generate", admin_token, org["id"],
        json={
            "name": "Morning round",
            "service_date": str(date.today()),
            "depot_lat": 12.94, "depot_lng": 77.60,
            "vehicle_ids": [vehicle["id"]],
        },
    )
    assert r.status_code == 201, r.text
    route = r.json()
    assert route["stops_count"] == 12
    assert len(route["stops"]) == 12
    assert route["optimization"]["solver"] == "ortools-cvrp"
    assert route["optimization"]["geometry_estimated"] is True  # OSRM not configured in tests
    assert route["geometry"]["type"] == "LineString"
    assert route["total_distance_km"] > 0
    # sequence numbers ordered
    seqs = [s["sequence_no"] for s in route["stops"]]
    assert seqs == sorted(seqs)


async def test_capacity_constraint_respected(client):
    """Two vehicles with tight capacity must split the load; demand is never exceeded."""
    from app.routing.optimizer import StopSpec, VehicleSpec, solve

    stops = [
        StopSpec(key=f"s{i}", lat=12.94 + i * 0.001, lng=77.60 + i * 0.001, demand_kg=600)
        for i in range(10)
    ]  # total demand 6000 kg
    result = solve(depot=(12.94, 77.60), stops=stops, vehicles=[VehicleSpec("v1", 3000), VehicleSpec("v2", 3000)])
    assert result.solver_status != "no_solution"
    assert len(result.unassigned) == 0
    for plan in result.plans:
        assert plan.load_kg <= 3000.0
    served = sum(len(p.stop_keys) for p in result.plans)
    assert served == 10


async def test_unservicable_demand_is_reported_not_silent(client):
    from app.routing.optimizer import StopSpec, VehicleSpec, solve

    stops = [StopSpec(key="heavy", lat=12.95, lng=77.61, demand_kg=99999)]
    result = solve(depot=(12.94, 77.60), stops=stops, vehicles=[VehicleSpec("v1", 5000)])
    assert "heavy" in result.unassigned


async def test_route_with_no_points_fails_gracefully(client):
    org, admin_token = await make_org_with_admin(client)
    vehicle = await _make_vehicle(client, admin_token, org["id"], "RV-2")
    r = await api(
        client, "POST", "/api/v1/routes/generate", admin_token, org["id"],
        json={
            "name": "Empty", "service_date": str(date.today()),
            "depot_lat": 12.94, "depot_lng": 77.60, "vehicle_ids": [vehicle["id"]],
            "zone_id": str(uuid.uuid4()),  # no such zone => no points
        },
    )
    assert r.status_code == 422


async def test_field_stop_execution_updates_collection_event(client):
    org, admin_token = await make_org_with_admin(client)
    point = await create_point(client, admin_token, org["id"], 12.945, 77.605)
    vehicle = await _make_vehicle(client, admin_token, org["id"], "RV-3")

    today = date.today()
    # Create today's scheduled event for the point
    from app.collection.models import CollectionEvent, EventStatus
    from app.core.db import SessionLocal, tenant_context

    async with SessionLocal() as session:
        with tenant_context(session, uuid.UUID(org["id"])):
            session.add(
                CollectionEvent(
                    organization_id=uuid.UUID(org["id"]),
                    collection_point_id=uuid.UUID(point["id"]),
                    scheduled_date=today,
                    status=EventStatus.scheduled,
                )
            )
            await session.commit()

    route = (
        await api(
            client, "POST", "/api/v1/routes/generate", admin_token, org["id"],
            json={"name": "Field round", "service_date": str(today),
                  "depot_lat": 12.94, "depot_lng": 77.60, "vehicle_ids": [vehicle["id"]]},
        )
    ).json()
    stop = route["stops"][0]

    collector, collector_token = await __import__("conftest").add_member(
        client, admin_token, org["id"], role="collector"
    )
    r = await api(
        client, "PATCH", f"/api/v1/routes/stops/{stop['id']}", collector_token, org["id"],
        json={"status": "completed", "weight_kg": 210.5},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "completed"

    events = await api(
        client, "GET", "/api/v1/collection/events", admin_token, org["id"],
        params={"date_from": str(today), "date_to": str(today)},
    )
    matching = [e for e in events.json()["items"] if e["collection_point_id"] == point["id"]]
    assert matching and matching[0]["status"] == "completed"
    assert float(matching[0]["weight_kg"]) == 210.5


# --- Sustainability ------------------------------------------------------------


async def test_emission_factor_seed_and_recompute(client):
    from app.core.db import SessionLocal
    from app.sustainability.service import recompute_period, seed_emission_factors

    org, admin_token = await make_org_with_admin(client)
    async with SessionLocal() as session:
        created = await seed_emission_factors(session)
        await session.commit()
        assert created >= 0  # idempotent

    # Activity data: 1000 kg recyclable + 500 kg landfill today
    from datetime import timedelta

    from app.sustainability.models import DataQuality, WasteTreatment

    end = date.today()
    start = end - timedelta(days=6)  # matches API window days=7
    async with SessionLocal() as session:
        from app.core.db import tenant_context

        with tenant_context(session, uuid.UUID(org["id"])):
            session.add(
                WasteTreatment(
                    organization_id=uuid.UUID(org["id"]), treatment_date=end,
                    waste_category_id=None, destination="recycling", weight_kg=1000,
                    quality=DataQuality.measured,
                )
            )
            session.add(
                WasteTreatment(
                    organization_id=uuid.UUID(org["id"]), treatment_date=end,
                    waste_category_id=None, destination="landfill", weight_kg=500,
                    quality=DataQuality.measured,
                )
            )
            await session.commit()
            summary = await recompute_period(
                session, organization_id=uuid.UUID(org["id"]), period_start=start, period_end=end
            )
            await session.commit()

    assert summary["total_collected_kg"] == 1500.0
    assert summary["diverted_kg"] == 1000.0
    assert abs(summary["diversion_rate"] - 1000 / 1500) < 0.001
    # treatment emissions: 1 t recycling × 80 + 0.5 t landfill × 580 = 370 kg
    assert abs(summary["total_co2e_kg"] - (80.0 + 0.5 * 580.0)) < 1.0
    # avoided (modelled): 1 t × (580 − 80) = 500 kg
    assert abs(summary["avoided_kg_modeled"] - 500.0) < 1.0

    # Every record carries methodology + factor provenance
    r = await api(client, "GET", "/api/v1/sustainability/summary", admin_token, org["id"], params={"days": 7})
    assert r.status_code == 200
    data = r.json()
    assert data["emissions"]["total_co2e_kg"] > 0
    for rec in data["records"]:
        assert rec["methodology"]
        assert rec["quality"] in ("measured", "estimated", "modeled")


async def test_fleet_emissions_are_labelled_estimated(client):
    """Distance-based fleet factors must be labelled estimated with assumptions."""
    org, admin_token = await make_org_with_admin(client)
    from datetime import timedelta

    from app.core.db import SessionLocal, tenant_context
    from app.routing.models import Route, RouteStatus
    from app.sustainability.service import recompute_period, seed_emission_factors

    end = date.today()
    async with SessionLocal() as session:
        await seed_emission_factors(session)
        await session.commit()
        with tenant_context(session, uuid.UUID(org["id"])):
            session.add(
                Route(
                    organization_id=uuid.UUID(org["id"]), code="RT-TEST-1", name="Test route",
                    service_date=end, status=RouteStatus.completed,
                    depot_lat=12.94, depot_lng=77.60, total_distance_km=100.0,
                    stops_count=5,
                )
            )
            await session.commit()
            await recompute_period(
                session, organization_id=uuid.UUID(org["id"]),
                period_start=end - timedelta(days=1), period_end=end,
            )
            await session.commit()
    r = await api(client, "GET", "/api/v1/sustainability/summary", admin_token, org["id"], params={"days": 2})
    recs = r.json()["records"]
    fleet = [x for x in recs if x["category"].startswith("fleet_")]
    assert fleet, "expected a fleet emission record"
    for f in fleet:
        assert f["quality"] == "estimated"
        assert f["scope"] == "scope1"
        assert "assumed_consumption_l_per_km" in f["assumptions"]
