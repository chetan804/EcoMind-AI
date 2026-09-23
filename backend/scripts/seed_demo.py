#!/usr/bin/env python
"""Seed a clearly-labelled DEMO organization with synthetic data.

Everything synthetic is flagged: the organization is ``is_demo``, simulated
devices/telemetry carry ``is_simulated`` / ``source='simulator'``, and demo AI
inferences are ``is_simulated``. The UI surfaces DEMO / SIMULATION badges from
these flags — demo data never masquerades as production data.

Usage:  python scripts/seed_demo.py [--reset]
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

import app.models  # noqa: E402,F401 — full metadata for FK resolution
from app.core.db import SessionLocal, tenant_context, unscoped, utcnow  # noqa: E402
from app.core.security import hash_password  # noqa: E402

DEMO_PASSWORD = "EcoDemo2026!"
DEMO_SLUG = "aurora-demo"

random.seed(20260923)

ZONES = [
    ("Z-CN", "Cinder Park", "#10b981", 12.9630, 77.5850, 0.016),
    ("Z-RV", "Riverline", "#3b82f6", 12.9480, 77.6150, 0.018),
    ("Z-HB", "Harbourview", "#f59e0b", 12.9750, 77.6200, 0.014),
    ("Z-ND", "Northgate", "#a855f7", 12.9840, 77.5900, 0.015),
]

STAFF = [
    ("admin@aurora.demo", "Priya Raghavan", "org_admin"),
    ("ops@aurora.demo", "Marcus Oduya", "ops_manager"),
    ("supervisor@aurora.demo", "Elena Fischer", "field_supervisor"),
    ("analyst@aurora.demo", "David Kim", "sustainability_analyst"),
]
DRIVERS = [
    ("driver1@aurora.demo", "Ravi Chandran", "DL-04-2019-0041821"),
    ("driver2@aurora.demo", "Sunita Meka", "DL-04-2020-0077542"),
    ("driver3@aurora.demo", "Tomas Alvarez", "DL-04-2018-0011233"),
]
CITIZEN_NAMES = [
    "Aisha Khan", "Ben Osei", "Chen Wei", "Diana Marquez", "Erik Larsson",
    "Fatima Noor", "Gabriel Silva", "Hana Suzuki", "Ibrahim Toure", "Julia Novak",
    "Kwame Mensah", "Lena Petrova", "Miguel Santos", "Nadia Hassan", "Omar Farouk",
]
VEHICLES = [
    ("TV-01", "Compactor 01", "compactor_truck", "diesel", 9000, 18),
    ("TV-02", "Compactor 02", "compactor_truck", "diesel", 9000, 18),
    ("TV-03", "Tipper 03", "tipper_truck", "diesel", 7000, 12),
    ("EV-04", "EV Van 04", "ev_van", "electric", 2500, 8),
    ("EV-05", "EV Van 05", "ev_van", "electric", 2500, 8),
    ("CV-06", "City Van 06", "van", "cng", 1800, 6),
]

REPORT_DESCRIPTIONS = [
    ("Heap of plastic bottles and cardboard boxes dumped beside the bus stop", "recyclable", "medium"),
    ("Household garbage bags scattered near the park entrance after pickup was missed", "mixed", "high"),
    ("Old electronics — a monitor and cables — abandoned in the alley", "e_waste", "medium"),
    ("Food waste and garden leaves piled at the corner, strong smell", "organic", "medium"),
    ("Construction debris and rubble blocking the footpath", "construction", "high"),
    ("Used batteries and paint cans discarded next to the school wall", "hazardous", "urgent"),
    ("Overflowing public bin at the market square, waste on the street", "mixed", "high"),
    ("Glass shards in a bag near the children's playground", "recyclable", "high"),
]

COMPLAINTS = [
    ("Collection missed on Tuesday for the whole street", "missed_collection", "high"),
    ("Bin at the corner is cracked and leaking", "bin_damaged", "medium"),
    ("Terrible smell from the bin station all weekend", "odor", "medium"),
    ("Illegal dumping of furniture at the vacant lot", "illegal_dumping", "high"),
    ("Waste truck skipped our lane again", "missed_collection", "high"),
    ("Overflowing bins near the metro station", "overflow", "urgent"),
]


async def reset(session, slug: str) -> None:
    from sqlalchemy import select

    from app.orgs.models import Organization

    with unscoped(session):
        org = (
            await session.execute(select(Organization).where(Organization.slug == slug))
        ).scalar_one_or_none()
    from sqlalchemy import text

    from app.core.db import engine

    async with engine.begin() as conn:
        if org is not None:
            # ON DELETE CASCADE on organization_id clears tenant rows.
            await conn.execute(text(f"DELETE FROM organizations WHERE id = '{org.id}'"))
        # Users are not org-scoped (memberships cascade with the org, users don't):
        # remove the demo users by their reserved demo email domain so the seeder
        # is fully re-runnable. Per-user rows (notifications, tokens) cascade.
        await conn.execute(text("DELETE FROM users WHERE email LIKE '%@aurora.demo'"))
    print(f"removed existing demo org {slug} and demo users")


async def main(reset_first: bool) -> None:
    from app.ai.models import AiInference, AiStatus, AiTask
    from app.auth.models import User
    from app.collection.models import CollectionEvent, CollectionPoint, EventStatus, PointKind
    from app.complaints.models import Complaint, ComplaintCategory, ComplaintPriority, ComplaintStatus
    from app.fleet.models import DriverProfile, FuelType, Vehicle, VehicleStatus, VehicleType
    from app.iot.models import Alert, AlertSeverity, AlertStatus, Device, DeviceKind, TelemetryReading, TelemetrySource
    from app.notifications.models import Notification, NotificationCategory
    from app.orgs.models import OrgMembership
    from app.orgs.service import create_organization
    from app.rewards.models import RewardLedger, RewardReason
    from app.routing.models import Route, RouteStatus, RouteStop, StopStatus
    from app.sustainability.models import DataQuality, WasteTreatment
    from app.sustainability.service import seed_emission_factors
    from app.waste.models import (
        ReportSeverity,
        ReportSource,
        ReportStatus,
        WasteCategory,
        WasteReport,
        WasteReportEvent,
    )

    async with SessionLocal() as session:
        await seed_emission_factors(session)
        await session.commit()

        if reset_first:
            await reset(session, DEMO_SLUG)

        # --- Organization -----------------------------------------------------
        admin_user = User(
            email=STAFF[0][0], full_name=STAFF[0][1], password_hash=hash_password(DEMO_PASSWORD)
        )
        session.add(admin_user)
        await session.flush()
        with unscoped(session):
            org = await create_organization(
                session,
                name="Aurora Municipal Corporation",
                slug=DEMO_SLUG,
                org_type="municipal_corporation",
                creator_user_id=admin_user.id,
                timezone="Asia/Kolkata",
                city="Aurora",
                country="Demo",
                contact_email="hello@aurora.demo",
                is_demo=True,
            )
            org.allow_anonymous_reports = True
            org.settings = {
                "ai_confidence_threshold": 0.75,
                "sla_hours": {"urgent": 12, "high": 24, "medium": 72, "low": 120},
            }
        await session.flush()
        org_id = org.id
        print("org:", org.name, org_id)

        with tenant_context(session, org_id):
            # --- Staff, drivers, citizens -------------------------------------
            staff_users = {}
            for email, name, role in STAFF[1:]:
                u = User(email=email, full_name=name, password_hash=hash_password(DEMO_PASSWORD))
                session.add(u)
                await session.flush()
                session.add(OrgMembership(user_id=u.id, organization_id=org_id, role_code=role))
                staff_users[role] = u
            driver_users = []
            for email, name, license_no in DRIVERS:
                u = User(email=email, full_name=name, password_hash=hash_password(DEMO_PASSWORD))
                session.add(u)
                await session.flush()
                session.add(OrgMembership(user_id=u.id, organization_id=org_id, role_code="collector"))
                session.add(
                    DriverProfile(
                        organization_id=org_id, user_id=u.id, license_number=license_no,
                        license_expiry=datetime(2028, 6, 30, tzinfo=None),
                    )
                )
                driver_users.append(u)
            citizens = []
            for i, name in enumerate(CITIZEN_NAMES):
                u = User(
                    email=f"citizen{i + 1}@aurora.demo",
                    full_name=name,
                    password_hash=hash_password(DEMO_PASSWORD),
                )
                session.add(u)
                await session.flush()
                session.add(OrgMembership(user_id=u.id, organization_id=org_id, role_code="citizen"))
                session.add(
                    RewardLedger(
                        organization_id=org_id, user_id=u.id, points=10,
                        reason=RewardReason.signup, description="Joined Aurora EcoMind",
                        awarded_at=utcnow() - timedelta(days=random.randint(5, 40)),
                    )
                )
                citizens.append(u)

            # --- Zones ---------------------------------------------------------
            from app.orgs.service import create_zone

            zones = []
            for code, name, color, lat, lng, span in ZONES:
                ring = [
                    [lng - span, lat - span * 0.8], [lng + span, lat - span * 0.8],
                    [lng + span, lat + span * 0.8], [lng - span, lat + span * 0.8],
                    [lng - span, lat - span * 0.8],
                ]
                z = await create_zone(
                    session, org_id, name=name, code=code, color_hex=color,
                    boundary={"type": "Polygon", "coordinates": [ring]},
                )
                zones.append(z)
            await session.flush()

            # --- Collection points ----------------------------------------------
            points = []
            for zi, (_, _, _, zlat, zlng, zspan) in enumerate(ZONES):
                for i in range(13):
                    lat = zlat + random.uniform(-zspan * 0.75, zspan * 0.75)
                    lng = zlng + random.uniform(-zspan, zspan)
                    p = CollectionPoint(
                        organization_id=org_id,
                        code=f"CP-{zi + 1}{i + 1:02d}",
                        name=f"{ZONES[zi][1]} Station {i + 1:02d}",
                        kind=PointKind.bin_station,
                        zone_id=zones[zi].id,
                        latitude=round(lat, 6),
                        longitude=round(lng, 6),
                        address=(
                            f"{random.randint(1, 99)} "
                            f"{random.choice(['Maple', 'Cedar', 'Birch', 'Willow', 'Aspen'])} Street, {ZONES[zi][1]}"
                        ),
                        households_served=random.randint(40, 300),
                        capacity_volume_m3=random.choice([1.1, 2.5, 3.2, 4.5]),
                        est_fill_pct=random.randint(20, 80),
                    )
                    session.add(p)
                    points.append(p)
            await session.flush()

            # --- Vehicles --------------------------------------------------------
            vehicles = []
            for code, name, vtype, fuel, cap, vol in VEHICLES:
                v = Vehicle(
                    organization_id=org_id, code=code, name=name,
                    vehicle_type=VehicleType(vtype), fuel_type=FuelType(fuel),
                    plate_number=f"KA-01-{random.randint(1000, 9999)}",
                    capacity_kg=cap, capacity_volume_m3=vol,
                    status=VehicleStatus.active,
                    depot_lat=12.9568, depot_lng=77.6010,
                    current_lat=12.9568 + random.uniform(-0.01, 0.01),
                    current_lng=77.6010 + random.uniform(-0.01, 0.01),
                    position_is_simulated=True,
                    odometer_km=random.randint(20000, 90000),
                )
                session.add(v)
                vehicles.append(v)
            await session.flush()

            # --- Simulated smart-bin devices --------------------------------------
            sim_devices = []
            for i in range(14):
                p = points[i * 3]
                d = Device(
                    organization_id=org_id,
                    device_key=f"SIM-BIN-{i + 1:03d}",
                    name=f"SIM Bin Sensor {i + 1:03d}",
                    kind=DeviceKind.fill_sensor,
                    api_key_hash=hash_password(f"simkey-{i}")[:64].replace("$", "a"),
                    api_key_prefix="sim",
                    status="active",
                    collection_point_id=p.id,
                    zone_id=p.zone_id,
                    latitude=p.latitude,
                    longitude=p.longitude,
                    firmware="2.4.1",
                    is_simulated=True,
                )
                session.add(d)
                sim_devices.append(d)
            await session.flush()

            # Simulated telemetry history (5 days, ~4-hour cadence)
            now = utcnow()
            for d in sim_devices:
                fill = random.uniform(15, 45)
                battery = random.uniform(75, 100)
                t = now - timedelta(days=5)
                while t < now:
                    fill = min(100, fill + random.uniform(4, 11))
                    if random.random() < 0.18:
                        fill = random.uniform(5, 25)  # collection reset
                    battery = max(8, battery - random.uniform(0.15, 0.5))
                    temp = random.uniform(19, 34)
                    session.add(
                        TelemetryReading(
                            organization_id=org_id, device_id=d.id, recorded_at=t,
                            fill_pct=round(fill, 1), temperature_c=round(temp, 1),
                            battery_pct=round(battery, 1),
                            signal_strength_dbm=round(random.uniform(-92, -55), 1),
                            source=TelemetrySource.simulator, is_simulated=True,
                        )
                    )
                    t += timedelta(hours=4)
                d.current_fill_pct = round(fill, 1)
                d.current_battery_pct = round(battery, 1)
                d.current_temperature_c = round(random.uniform(20, 32), 1)
                d.last_telemetry_at = now - timedelta(minutes=random.randint(2, 40))
            await session.flush()

            # --- Waste reports with lifecycle + labelled simulated AI inferences ----
            categories = {
                c.code: c for c in (
                    await session.execute(
                        select(WasteCategory).where(WasteCategory.organization_id == org_id)
                    )
                ).scalars().all()
            }
            reports = []
            for _ in range(38):
                desc, cat_code, severity = random.choice(REPORT_DESCRIPTIONS)
                age_days = random.randint(0, 29)
                created = utcnow() - timedelta(days=age_days, hours=random.randint(0, 20))
                zone = random.choice(zones)
                p = random.choice(points)
                reporter = random.choice(citizens) if random.random() < 0.85 else None
                status = random.choices(
                    [ReportStatus.resolved, ReportStatus.in_progress, ReportStatus.submitted, ReportStatus.rejected],
                    weights=[0.55, 0.2, 0.2, 0.05],
                )[0]
                r = WasteReport(
                    organization_id=org_id,
                    reporter_user_id=reporter.id if reporter else None,
                    is_anonymous=reporter is None,
                    description=desc,
                    category_guess=cat_code,
                    confirmed_category_id=categories[cat_code].id if random.random() < 0.7 else None,
                    latitude=round(p.latitude + random.uniform(-0.004, 0.004), 6),
                    longitude=round(p.longitude + random.uniform(-0.004, 0.004), 6),
                    address=p.address,
                    zone_id=zone.id,
                    status=status,
                    severity=ReportSeverity(severity),
                    source=random.choice([ReportSource.citizen_app, ReportSource.web]),
                    created_at=created,
                )
                session.add(r)
                await session.flush()
                session.add(
                    WasteReportEvent(
                        organization_id=org_id, report_id=r.id, event_type="created",
                        actor_user_id=reporter.id if reporter else None,
                        to_status="submitted", note=desc, created_at=created,
                    )
                )
                # Labelled simulated AI inference
                confidence = random.uniform(0.78, 0.97) if random.random() < 0.8 else random.uniform(0.3, 0.6)
                inf = AiInference(
                    organization_id=org_id,
                    task=AiTask.waste_classification,
                    status=AiStatus.succeeded if confidence >= 0.75 else AiStatus.needs_review,
                    provider="openai" if random.random() < 0.5 else "anthropic",
                    model="gpt-4o-mini" if random.random() < 0.5 else "claude-sonnet-4",
                    input_type="image",
                    input_summary=desc[:120],
                    input_ref=r.id,
                    output={
                        "category": cat_code,
                        "contamination_detected": random.random() < 0.2,
                        "estimated_volume_m3": round(random.uniform(0.02, 1.4), 2),
                        "handling_guidance": categories[cat_code].default_handling_guidance or "Standard handling.",
                        "confidence": round(confidence, 2),
                        "observations": ["demo dataset — simulated inference"],
                    },
                    confidence=round(confidence, 2),
                    latency_ms=random.randint(700, 2600),
                    is_simulated=True,
                )
                session.add(inf)
                await session.flush()
                r.ai_inference_id = inf.id
                if status == ReportStatus.resolved:
                    r.resolved_at = created + timedelta(hours=random.randint(4, 72))
                    r.resolution_notes = random.choice(
                        ["Crew collected the waste.", "Area cleaned and bin replaced.",
                         "Waste collected and site inspected."]
                    )
                    session.add(
                        WasteReportEvent(
                            organization_id=org_id, report_id=r.id, event_type="status_change",
                            from_status="in_progress", to_status="resolved",
                            note=r.resolution_notes, created_at=r.resolved_at,
                        )
                    )
                    if reporter:
                        session.add(
                            RewardLedger(
                                organization_id=org_id, user_id=reporter.id, points=25,
                                reason=RewardReason.report_resolved,
                                description="Your report was resolved",
                                reference_type="waste_report", reference_id=r.id,
                                awarded_at=r.resolved_at,
                            )
                        )
                reports.append(r)
            await session.flush()

            # --- Complaints --------------------------------------------------------
            for i, (subject, cat, prio) in enumerate(COMPLAINTS * 3):
                created = utcnow() - timedelta(days=random.randint(0, 25), hours=random.randint(1, 20))
                status = random.choices(
                    [
                        ComplaintStatus.resolved,
                        ComplaintStatus.in_progress,
                        ComplaintStatus.submitted,
                        ComplaintStatus.closed,
                    ],
                    weights=[0.5, 0.2, 0.2, 0.1],
                )[0]
                reporter = random.choice(citizens)
                c = Complaint(
                    organization_id=org_id,
                    reporter_user_id=reporter.id,
                    subject=subject,
                    description=f"{subject}. This is a demo complaint record for {ZONES[i % 4][1]}.",
                    category=ComplaintCategory(cat),
                    status=status,
                    priority=ComplaintPriority(prio),
                    zone_id=zones[i % 4].id,
                    due_at=created + timedelta(hours={"urgent": 12, "high": 24, "medium": 72, "low": 120}[prio]),
                    created_at=created,
                )
                if status in (ComplaintStatus.resolved, ComplaintStatus.closed):
                    c.resolved_at = created + timedelta(hours=random.randint(6, 80))
                    c.resolution_summary = "Resolved by the field team."
                    c.satisfaction_rating = random.randint(3, 5)
                session.add(c)
            await session.flush()

            # --- Collection events + treatments (30 days) ----------------------------
            today = date.today()
            events = []
            for day_offset in range(30, -1, -1):
                d = today - timedelta(days=day_offset)
                for p in points:
                    even_bin = hash(p.id) % 2 == 0
                    if (even_bin and d.weekday() in (1, 4)) or (not even_bin and d.weekday() in (2, 5)):
                        status = EventStatus.completed if random.random() > 0.06 else EventStatus.missed
                        e = CollectionEvent(
                            organization_id=org_id,
                            collection_point_id=p.id,
                            waste_category_id=random.choice(
                                [categories["mixed"].id, categories["recyclable"].id, categories["organic"].id]
                            ),
                            scheduled_date=d,
                            status=status,
                            vehicle_id=random.choice(vehicles).id,
                            collector_user_id=random.choice(driver_users).id,
                        )
                        if status == EventStatus.completed:
                            e.completed_at = datetime(d.year, d.month, d.day, random.randint(7, 15))
                            e.weight_kg = round(random.uniform(60, 420), 1)
                        events.append(e)
            session.add_all(events)
            await session.flush()

            # Treatments derived from completed events (activity data, measured)
            for e in events:
                if e.status != EventStatus.completed or not e.weight_kg:
                    continue
                cat = (
                    await session.execute(
                        select(WasteCategory).where(WasteCategory.id == e.waste_category_id)
                    )
                ).scalar_one()
                destinations = {"mixed": "landfill", "recyclable": "recycling", "organic": "composting"}
                destination = destinations.get(cat.code, "landfill")
                session.add(
                    WasteTreatment(
                        organization_id=org_id,
                        treatment_date=e.scheduled_date,
                        waste_category_id=e.waste_category_id,
                        destination=destination,
                        weight_kg=e.weight_kg,
                        quality=DataQuality.measured,
                        source_event_id=e.id,
                    )
                )
            await session.flush()

            # --- Routes (completed, with stops) ---------------------------------------
            for ri in range(4):
                d = today - timedelta(days=ri)
                v = vehicles[ri % len(vehicles)]
                driver = driver_users[ri % len(driver_users)]
                route_points = random.sample(points, 11)
                route = Route(
                    organization_id=org_id,
                    code=f"RT-{d.strftime('%y%m%d')}-{ri + 1:03d}",
                    name=f"{ZONES[ri % 4][1]} collection round",
                    service_date=d,
                    status=RouteStatus.completed if ri > 0 else RouteStatus.in_progress,
                    zone_id=zones[ri % 4].id,
                    vehicle_id=v.id,
                    driver_user_id=driver.id,
                    depot_lat=12.9568, depot_lng=77.6010,
                    total_distance_km=round(random.uniform(14, 26), 1),
                    total_duration_min=round(random.uniform(120, 220), 1),
                    planned_weight_kg=round(random.uniform(1500, 4000), 1),
                    stops_count=len(route_points),
                    optimization={
                        "solver": "ortools-cvrp", "solver_status": "optimal_found",
                        "solve_ms": random.randint(120, 900), "geometry_provider": "estimated-straightline",
                        "geometry_estimated": True, "road_distance_factor": 1.3,
                        "unassigned_stops": [], "vehicles_used": 1,
                    },
                    geometry={
                        "type": "LineString",
                        "coordinates": [[12.9568, 77.6010]]
                        + [[p.latitude, p.longitude] for p in route_points]
                        + [[12.9568, 77.6010]],
                    },
                    geometry_is_estimated=True,
                    created_by=staff_users["ops_manager"].id,
                    started_at=datetime(d.year, d.month, d.day, 7, 30),
                    completed_at=datetime(d.year, d.month, d.day, 12, 45) if ri > 0 else None,
                )
                session.add(route)
                await session.flush()
                for seq, p in enumerate(route_points, start=1):
                    st = StopStatus.completed if (ri > 0 and random.random() > 0.08) else StopStatus.pending
                    session.add(
                        RouteStop(
                            organization_id=org_id, route_id=route.id, sequence_no=seq,
                            collection_point_id=p.id,
                            planned_arrival_offset_min=seq * random.randint(9, 16),
                            est_distance_from_prev_km=round(random.uniform(0.4, 2.2), 2),
                            est_duration_from_prev_min=round(random.uniform(2, 8), 1),
                            status=st,
                            completed_at=(
                                datetime(d.year, d.month, d.day, 8, seq * 15 % 60)
                                if st == StopStatus.completed
                                else None
                            ),
                            weight_kg=round(random.uniform(60, 300), 1) if st == StopStatus.completed else None,
                            created_at=datetime(d.year, d.month, d.day, 6, 0),
                        )
                    )
                v.current_route_id = route.id if ri == 0 else v.current_route_id
            await session.flush()

            # --- Alerts from simulated telemetry ---------------------------------------
            for _ in range(9):
                sev = random.choice([AlertSeverity.warning, AlertSeverity.high, AlertSeverity.critical])
                d = random.choice(sim_devices)
                session.add(
                    Alert(
                        organization_id=org_id,
                        device_id=d.id,
                        severity=sev,
                        title=(
                            f"{'Overflow risk' if sev != AlertSeverity.critical else 'High temperature (fire risk)'}"
                            f": {d.name}"
                        ),
                        message=f"SIMULATED DEMO DATA — device {d.device_key} reported "
                                f"{'fill 91%' if sev != AlertSeverity.critical else 'temperature 57.2°C'}.",
                        status=AlertStatus.open if random.random() < 0.5 else AlertStatus.resolved,
                        triggered_at=utcnow() - timedelta(hours=random.randint(1, 96)),
                        metadata={"value": 91 if sev != AlertSeverity.critical else 57.2, "demo": True},
                    )
                )
            await session.flush()

            # --- Notifications ------------------------------------------------------------
            titles = [
                ("Waste collection in your zone tomorrow", "collection"),
                ("Your report was resolved", "report_update"),
                ("New sustainability points earned", "reward"),
                ("Aurora demo: simulated alert raised", "alert"),
            ]
            for u in citizens[:10]:
                t, cat = random.choice(titles)
                session.add(
                    Notification(
                        organization_id=org_id, recipient_user_id=u.id,
                        category=NotificationCategory(cat.replace("collection", "system")),
                        title=t, body="Demo notification generated by the seed script.",
                        data={"demo": True},
                        read_at=utcnow() - timedelta(hours=2) if random.random() < 0.4 else None,
                    )
                )
            await session.commit()

            # --- Sustainability recompute ---------------------------------------------------
            from app.sustainability.service import recompute_period

            result = await recompute_period(
                session, organization_id=org_id,
                period_start=today - timedelta(days=29), period_end=today,
            )
            await session.commit()
            print("sustainability:", result)

        print("\nDEMO SEED COMPLETE")
        print(f"  org: {DEMO_SLUG} (is_demo=True)")
        print(f"  staff login: admin@aurora.demo / {DEMO_PASSWORD}")
        print(f"  ops login:   ops@aurora.demo / {DEMO_PASSWORD}")
        print(f"  driver:      driver1@aurora.demo / {DEMO_PASSWORD}")
        print(f"  citizen:     citizen1@aurora.demo / {DEMO_PASSWORD}")
        print(f"  analyst:     analyst@aurora.demo / {DEMO_PASSWORD}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(reset_first=args.reset))
