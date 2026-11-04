"""One day of synthetic operations, as rows for every table.

A day is generated from its own random streams and from a small running state (citizen reward
balances), so the same (seed, profile, anchor) always gives the same rows. Days are generated in
order; the loader may skip days that are already stored and still gets the identical state.

Chain per collection task, in time order:
  citizen -> waste report -> manager creates task -> manager assigns collector + vehicle ->
  collector arrives, collects (weight), unloads at a facility -> reporter earns points ->
  facility records recovery -> operator verifies -> material passport custody chain ->
  optional marketplace listing; plus failed, cancelled, contaminated and still-open work.
"""

from __future__ import annotations

import datetime as dt
import math
import uuid
from collections import defaultdict
from dataclasses import dataclass

from .geography import BY_NAME, bearing_deg, haversine_km
from .ids import sid, stream
from .world import IST, LABEL, Facility, World

TABLES = (
    "waste_reports", "collection_tasks", "collection_assignments", "collection_task_status_history",
    "collection_events", "route_plans", "route_stops", "vehicle_location_events", "recovery_records",
    "material_passports", "custody_events", "reward_ledger_entries", "reward_redemptions",
    "notifications", "community_incidents", "marketplace_listings", "marketplace_requests",
)  # fmt: skip

KINDS = (  # (title, kg range, share, material weights key)
    ("Overflowing community bin", (60, 350), 0.34, "household"),
    ("Roadside garbage pile", (150, 900), 0.24, "household"),
    ("Mixed waste at the market", (300, 1400), 0.14, "market"),
    ("Construction debris", (500, 3000), 0.06, "debris"),
    ("Garden and organic waste", (80, 500), 0.10, "organic"),
    ("Dry waste bags", (25, 200), 0.08, "dry"),
    ("Electronic waste", (20, 150), 0.02, "ewaste"),
    ("Textile and bulky items", (40, 400), 0.02, "textile"),
)  # fmt: skip
MATERIALS = {  # kind -> ((category code, weight), ...)
    "household": (("organic", 40), ("plastic", 16), ("paper", 9), ("cardboard", 8), ("glass", 5), ("metal", 4), ("textile", 4), ("trash", 14)),
    "market": (("organic", 62), ("cardboard", 12), ("plastic", 12), ("trash", 10), ("paper", 4)),
    "debris": (("trash", 60), ("metal", 20), ("glass", 10), ("plastic", 10)),
    "organic": (("organic", 95), ("trash", 5)),
    "dry": (("plastic", 34), ("paper", 24), ("cardboard", 20), ("glass", 8), ("metal", 8), ("textile", 6)),
    "ewaste": (("e_waste", 100),),
    "textile": (("textile", 85), ("trash", 15)),
}  # fmt: skip
METHOD = {
    "organic": ("composted", 0.50, 0.80), "plastic": ("recycled", 0.60, 0.88), "paper": ("recycled", 0.70, 0.92),
    "cardboard": ("recycled", 0.72, 0.93), "glass": ("recycled", 0.80, 0.95), "metal": ("recycled", 0.85, 0.97),
    "textile": ("reused", 0.55, 0.90), "e_waste": ("refurbished", 0.55, 0.90), "trash": ("energy_recovered", 0.35, 0.60),
    "medical": ("energy_recovered", 0.30, 0.50),
}  # fmt: skip
LISTING_CATEGORY = {
    "plastic": "plastics", "metal": "metals", "paper": "paper", "cardboard": "paper", "glass": "glass",
    "e_waste": "e_waste", "organic": "organics", "textile": "textiles",
}  # fmt: skip
INCIDENT_TYPES = (("illegal_dumping", 30), ("overflowing_bin", 34), ("missed_collection", 18), ("open_burning", 6), ("hazardous_waste", 4), ("other", 8))  # fmt: skip
SKIP_REASONS = ("Access blocked by parked vehicles", "Container already emptied", "No waste found at the location", "Gate locked, nobody to open it")  # fmt: skip
STREETS = ("Lane 2", "Lane 4", "Road No. 3", "Main Road", "Service Road", "Temple Street", "Market Lane", "Colony Road", "Bus Stop Road", "School Lane")  # fmt: skip
LAT_M = 111_320.0

Row = tuple[object, ...]


def pick(r, options):  # noqa: ANN001, ANN201 - tiny weighted choice helper
    total = sum(w for _, w in options)
    x = r.random() * total
    for value, weight in options:
        x -= weight
        if x <= 0:
            return value
    return options[-1][0]


@dataclass
class Task:
    id: uuid.UUID
    day: dt.date
    idx: int
    locality: str
    lat: float
    lon: float
    address: str
    title: str
    kind: str
    material_key: str
    weight: float
    priority: str
    created_at: dt.datetime
    status: str
    collector: int
    manager: uuid.UUID
    report_id: uuid.UUID | None
    citizen: int | None
    assigned_at: dt.datetime | None = None
    ended_at: dt.datetime | None = None
    destination: Facility | None = None
    arrival: dt.datetime | None = None
    collected_at: dt.datetime | None = None
    collected_kg: float | None = None
    updated_at: dt.datetime | None = None


class Simulator:
    def __init__(self, world: World) -> None:
        self.w = world
        self.balance: dict[int, int] = defaultdict(int)  # citizen index -> points
        self.eligible: set[int] = set()
        self.min_cost = min(c for _, _, c in world.item_ids)
        self.passport_no = 0
        r = stream(world.seed, "surges")
        n = world.profile.days
        starts = sorted(r.sample(range(int(n * 0.25), int(n * 0.9) - 7), 3))
        self.surge_weeks = {starts[0]: 1.9, starts[1]: 2.0}  # busy weeks
        self.dip_week = starts[2]  # a disrupted week with little collection
        self.first_day = world.anchor - dt.timedelta(days=n)

    # ------------------------------------------------------------------ volumes
    def volume(self, d: dt.date) -> int:
        w, p = self.w, self.w.profile
        i = (d - self.first_day).days
        weekday = (1.0, 1.0, 1.0, 1.0, 1.0, 0.7, 0.35)[d.weekday()]
        season = 1 + 0.12 * math.sin(2 * math.pi * d.timetuple().tm_yday / 365)
        trend = 1 + 0.15 * (i / max(1, p.days))
        noise = math.exp(stream(w.seed, "volume", d.isoformat()).gauss(0, 0.08))
        factor = 1.0
        for start, mult in self.surge_weeks.items():
            if start <= i < start + 7:
                factor = mult
        if self.dip_week <= i < self.dip_week + 7:
            factor = 0.35
        return max(1, round(p.tasks_per_day * weekday * season * trend * noise * factor))

    # ------------------------------------------------------------------ the day
    def day(self, d: dt.date) -> dict[str, list[Row]]:
        out: dict[str, list[Row]] = {t: [] for t in TABLES}
        w = self.w
        executed = d < w.anchor
        n = self.volume(d) if d <= w.anchor + dt.timedelta(days=2) else 0
        if not executed:
            n = max(1, n // 4)  # only what is already planned
        load: dict[int, int] = defaultdict(int)
        tasks: list[Task] = []
        for k in range(n):
            tasks.append(self._task(d, k, executed, load, out))
        if executed:
            self._execute(d, tasks, out)
        else:
            self._open_day(tasks, out)
        for t in tasks:
            self._task_rows(t, out)
        self._extra_reports(d, n, out)
        self._incidents(d, n, out)
        if executed:
            self._redemptions(d, out)
        return out

    # ------------------------------------------------------------------ task creation
    def _task(self, d: dt.date, k: int, executed: bool, load: dict[int, int], out: dict[str, list[Row]]) -> Task:
        w = self.w
        r = stream(w.seed, "task", d.isoformat(), k)
        locality = w.pick_locality(r.random())
        loc = BY_NAME[locality]
        lat = round(loc.lat + r.uniform(-0.011, 0.011), 6)
        lon = round(loc.lon + r.uniform(-0.011, 0.011), 6)
        title, (lo, hi), _, material_key = pick(r, [(kind, kind[2]) for kind in KINDS])
        weight = round(math.exp(r.uniform(math.log(lo), math.log(hi))), 1)
        depot = w.depot_of[locality]
        pool = w.pools[depot.code]
        for _ in range(6):
            collector = pool[r.randrange(len(pool))]
            if load[collector] < 9:
                break
        else:
            collector = min(pool, key=lambda c: load[c])
        load[collector] += 1
        capacity = w.vehicles[collector][2]
        weight = round(min(weight, capacity * 0.8), 1)
        lag = pick(r, [(1, 55), (2, 30), (3, 15)])
        base = dt.datetime.combine(d, dt.time(0, 0), tzinfo=IST) - dt.timedelta(days=lag)
        created = base + dt.timedelta(hours=9, minutes=r.randrange(0, 480))
        created = min(created, w.now_ts - dt.timedelta(minutes=10 + r.randrange(0, 600)))
        if executed:
            status = pick(r, [("completed", 84), ("failed", 7), ("cancelled", 9)])
        else:
            status = pick(r, [("pending", 40), ("assigned", 60)])
        has_report = r.random() < 0.84
        citizen = int(len(w.citizens) * r.random() ** 1.7) if has_report else None
        street = r.choice(STREETS)
        return Task(
            sid(w.seed, "task", d.isoformat(), k), d, k, locality, lat, lon,
            f"{street}, {locality}, Hyderabad (synthetic address)", f"{title} - {locality}", title, material_key,
            weight, pick(r, [("normal", 70), ("high", 18), ("low", 8), ("urgent", 4)]), created, status, collector,
            w.managers[r.randrange(len(w.managers))],
            sid(w.seed, "report", d.isoformat(), k) if has_report else None, citizen,
        )  # fmt: skip

    # ------------------------------------------------------------------ open (not yet executed) work
    def _open_day(self, tasks: list[Task], out: dict[str, list[Row]]) -> None:
        for t in tasks:
            r = stream(self.w.seed, "open", str(t.id))
            if t.status == "assigned":
                t.assigned_at = min(t.created_at + dt.timedelta(minutes=30 + r.randrange(0, 200)), self.w.now_ts - dt.timedelta(minutes=5))
                t.updated_at = t.assigned_at
            else:
                t.updated_at = t.created_at

    # ------------------------------------------------------------------ executed days
    def _execute(self, d: dt.date, tasks: list[Task], out: dict[str, list[Row]]) -> None:
        w = self.w
        by_collector: dict[int, list[Task]] = defaultdict(list)
        for t in tasks:
            r = stream(w.seed, "plan", str(t.id))
            t.assigned_at = t.created_at + dt.timedelta(minutes=20 + r.randrange(0, 240))
            if t.status == "cancelled":
                t.ended_at = t.assigned_at + dt.timedelta(hours=1 + r.randrange(0, 8))
                t.updated_at = t.ended_at
                continue
            by_collector[t.collector].append(t)
        for collector, stops in sorted(by_collector.items()):
            self._route(d, collector, stops, out)

    def _route(self, d: dt.date, collector: int, stops: list[Task], out: dict[str, list[Row]]) -> None:
        w = self.w
        depot = w.collector_depot[collector]
        vehicle_id, _, capacity, _, _ = w.vehicles[collector]
        r = stream(w.seed, "route", d.isoformat(), collector)
        # nearest-neighbour order from the depot: the order the crew is recorded as visiting
        order: list[Task] = []
        here = (depot.lat, depot.lon)
        remaining = list(stops)
        while remaining:
            nxt = min(remaining, key=lambda t: haversine_km(here[0], here[1], t.lat, t.lon))
            remaining.remove(nxt)
            order.append(nxt)
            here = (nxt.lat, nxt.lon)
        clock = dt.datetime.combine(d, dt.time(7, 0), tzinfo=IST) + dt.timedelta(minutes=r.randrange(0, 40))
        pos = (depot.lat, depot.lon)
        route_id = sid(w.seed, "route", d.isoformat(), collector)
        seq = 0
        km_total = 0.0
        stop_rows: list[Row] = []
        trip: list[Task] = []
        trip_kg = 0.0
        pings: list[tuple[float, float, dt.datetime, uuid.UUID | None]] = [(depot.lat, depot.lon, clock, None)]

        def leg(to_lat: float, to_lon: float, start: dt.datetime, task_id: uuid.UUID | None) -> dt.datetime:
            nonlocal km_total, pos
            km = haversine_km(pos[0], pos[1], to_lat, to_lon)
            km_total += km
            minutes = max(3.0, km * 1.35 / 22.0 * 60)  # straight-line x 1.35 at 22 km/h: a made-up speed
            n_mid = w.profile.pings_per_leg
            for j in range(1, n_mid + 1):
                f = j / (n_mid + 1)
                pings.append((pos[0] + (to_lat - pos[0]) * f, pos[1] + (to_lon - pos[1]) * f, start + dt.timedelta(minutes=minutes * f), None))  # fmt: skip
            arrive = start + dt.timedelta(minutes=minutes)
            pings.append((to_lat, to_lon, arrive, task_id))
            pos = (to_lat, to_lon)
            return arrive

        def unload(after: Task) -> None:
            nonlocal clock, seq, trip, trip_kg
            fac = w.transfer_of[after.locality] if trip_kg > capacity * 0.6 or r.random() < 0.3 else w.processing_of[after.locality]  # fmt: skip
            clock = leg(fac.lat, fac.lon, clock, None)
            clock += dt.timedelta(minutes=10 + r.randrange(0, 15))
            seq += 1
            stop_rows.append((sid(w.seed, "stop", str(route_id), seq), route_id, seq, None, fac.id, clock - dt.timedelta(minutes=r.randrange(0, 15)), clock, clock, clock))  # fmt: skip
            for member in trip:
                member.destination = fac
            out["collection_events"].append(
                (sid(w.seed, "event", str(after.id), "delivered"), after.id, "delivered_to_facility", clock, w.collectors[collector], fac.id,
                 round(trip_kg, 1), "Load unloaded (synthetic)", None, None, clock, clock)
            )  # fmt: skip
            trip, trip_kg = [], 0.0

        last: Task | None = None
        for t in order:
            if trip_kg + t.weight > capacity * 0.9 and last is not None and trip:
                unload(last)
            t.arrival = leg(t.lat, t.lon, clock, t.id)
            seq += 1
            planned = t.arrival - dt.timedelta(minutes=r.randrange(-20, 15))
            stop_rows.append((sid(w.seed, "stop", str(route_id), seq), route_id, seq, t.id, None, planned, t.arrival, t.arrival, t.arrival))  # fmt: skip
            service = dt.timedelta(minutes=6 + r.randrange(0, 20))
            out["collection_events"].append((sid(w.seed, "event", str(t.id), "arrived"), t.id, "arrived", t.arrival, w.collectors[collector], None, None, None, None, None, t.arrival, t.arrival))  # fmt: skip
            if t.status == "failed":
                t.ended_at = t.arrival + dt.timedelta(minutes=4)
                reason = SKIP_REASONS[r.randrange(len(SKIP_REASONS))]
                out["collection_events"].append((sid(w.seed, "event", str(t.id), "skipped"), t.id, "skipped", t.ended_at, w.collectors[collector], None, None, reason, t.lat, t.lon, t.ended_at, t.ended_at))  # fmt: skip
                t.updated_at = t.ended_at
                t.destination = None
                clock = t.ended_at
            else:
                contaminated = r.random() < 0.08
                kg = round(t.weight * (r.uniform(0.7, 0.95) if contaminated else r.uniform(0.9, 1.0)), 1)
                t.collected_at = t.arrival + service
                t.collected_kg = kg
                t.ended_at = t.collected_at
                t.updated_at = t.collected_at
                if contaminated:
                    out["collection_events"].append((sid(w.seed, "event", str(t.id), "contaminated"), t.id, "contaminated", t.arrival + service / 2, w.collectors[collector], None, None, "Mixed with hazardous or non-target waste (synthetic)", t.lat, t.lon, t.arrival + service / 2, t.arrival + service / 2))  # fmt: skip
                out["collection_events"].append((sid(w.seed, "event", str(t.id), "collected"), t.id, "collected", t.collected_at, w.collectors[collector], None, kg, "Collected (synthetic)", t.lat, t.lon, t.collected_at, t.collected_at))  # fmt: skip
                trip.append(t)
                trip_kg += kg
                last = t
                clock = t.collected_at
        if trip and last is not None:
            unload(last)
        # back to the depot
        clock = leg(depot.lat, depot.lon, clock, None)
        for row in stop_rows:
            out["route_stops"].append(row)
        done = [t for t in order if t.status in ("completed", "failed")]
        if not done:
            return
        first = min(t.assigned_at for t in order if t.assigned_at)
        out["route_plans"].append((
            route_id, f"{LABEL} {d.isoformat()} {depot.name.replace(LABEL + ' ', '')} crew {collector + 1}", d, "completed",
            vehicle_id, w.collectors[collector], depot.id, depot.id, w.managers[0], round(km_total, 2), None, None,
            first, clock,
        ))  # fmt: skip
        # simulated GPS trace, labelled by its source ('simulator'); times are strictly increasing
        prev = None
        for lat, lon, ts, task_id in pings:
            if prev is not None and ts <= prev:
                ts = prev + dt.timedelta(seconds=1)
            heading = None
            out["vehicle_location_events"].append((
                sid(w.seed, "ping", str(route_id), len(out["vehicle_location_events"]), ts.isoformat()), vehicle_id, round(lat, 6), round(lon, 6),
                ts, ts, "simulator", "accepted", round(5 + 10 * r.random(), 1), round(8 + 28 * r.random(), 1), heading, None,
                task_id, route_id, None, ts, ts,
            ))  # fmt: skip
            prev = ts

    # ------------------------------------------------------------------ rows that depend on a finished task
    def _task_rows(self, t: Task, out: dict[str, list[Row]]) -> None:
        w = self.w
        r = stream(w.seed, "rows", str(t.id))
        mgr, coll = t.manager, w.collectors[t.collector]
        history: list[tuple[str | None, str, uuid.UUID, dt.datetime, str | None]] = [(None, "pending", mgr, t.created_at, None)]
        assignment = None
        if t.status != "pending" and t.assigned_at is not None:
            history.append(("pending", "assigned", mgr, t.assigned_at, None))
            vehicle = w.vehicles[t.collector][0]
            unassigned = t.ended_at if t.status in ("completed", "failed", "cancelled") else None
            if t.status != "cancelled" or r.random() < 0.4:
                assignment = (sid(w.seed, "assignment", str(t.id)), t.id, coll, vehicle if t.status != "cancelled" else None, mgr, t.assigned_at, unassigned, t.assigned_at, unassigned or t.assigned_at)  # fmt: skip
        if t.status in ("completed", "failed") and t.arrival is not None and t.ended_at is not None:
            history.append(("assigned", "in_progress", coll, t.arrival - dt.timedelta(minutes=2), None))
            note = None if t.status == "completed" else "Could not collect (see the skipped event)"
            history.append(("in_progress", t.status, coll, t.ended_at, note))
        elif t.status == "cancelled" and t.ended_at is not None:
            history.append(("assigned", "cancelled", mgr, t.ended_at, "Cancelled before the crew set out (synthetic)"))
        if t.status == "cancelled" and t.ended_at is None:
            raise AssertionError("cancelled task without an end time")
        for n, (frm, to, who, when, note) in enumerate(history):
            out["collection_task_status_history"].append((sid(w.seed, "history", str(t.id), n), t.id, frm, to, who, note, when, when))
        if assignment:
            out["collection_assignments"].append(assignment)
        dest = t.destination.id if t.destination and t.status == "completed" else None
        due = dt.datetime.combine(t.day, dt.time(18, 0), tzinfo=IST)
        updated = t.updated_at or t.created_at
        out["collection_tasks"].append((
            t.id, t.report_id, dest, mgr, t.title, t.status, t.priority, t.address, due,
            "Synthetic demonstration record.", t.lat, t.lon, t.created_at, updated,
        ))  # fmt: skip
        if t.report_id is not None and t.citizen is not None:
            reported = t.created_at - dt.timedelta(hours=3 + r.randrange(0, 50))
            rstatus = "closed" if t.status == "completed" else "verified"
            est = round(t.weight * r.uniform(0.7, 1.4), 1)
            out["waste_reports"].append((
                t.report_id, w.citizens[t.citizen], rstatus, f"{t.kind} at {t.locality}", "Synthetic demonstration report (not a real citizen report).",
                t.address, est, reported, t.lat, t.lon, None, None, reported, updated,
            ))  # fmt: skip
            self._notify_citizen(t, out, updated)
        if t.status in ("assigned", "in_progress", "completed", "failed") and t.assigned_at is not None:
            out["notifications"].append((
                sid(w.seed, "note", str(t.id), "assigned"), coll, "collection", "New collection task assigned", t.title, "collection_task", t.id,
                t.assigned_at + dt.timedelta(hours=2) if t.status in ("completed", "failed") else None, t.assigned_at, t.assigned_at,
            ))  # fmt: skip
        if t.status == "completed" and t.collected_kg and t.collected_at:
            self._after_collection(t, out, r)

    def _notify_citizen(self, t: Task, out: dict[str, list[Row]], when: dt.datetime) -> None:
        if t.status == "completed" and t.citizen is not None:
            r = stream(self.w.seed, "readnote", str(t.id))
            read = when + dt.timedelta(hours=1 + r.randrange(0, 30)) if r.random() < 0.6 else None
            out["notifications"].append((
                sid(self.w.seed, "note", str(t.id), "collected"), self.w.citizens[t.citizen], "report", "Your reported waste was collected",
                f"{t.title}: {t.collected_kg} kg collected", "waste_report", t.report_id, read, when, when,
            ))  # fmt: skip

    def _after_collection(self, t: Task, out: dict[str, list[Row]], r) -> None:  # noqa: ANN001
        w = self.w
        assert t.collected_at is not None and t.collected_kg is not None
        kg = t.collected_kg
        if t.citizen is not None and t.report_id is not None:
            points = max(1, round(kg * 10))
            entry = sid(w.seed, "ledger", str(t.id), "earned")
            out["reward_ledger_entries"].append((entry, w.citizens[t.citizen], "earned", points, kg, "collection_task", t.id, None, w.collectors[t.collector], "Waste collected from your report", t.collected_at, t.collected_at))  # fmt: skip
            self.balance[t.citizen] += points
            if self.balance[t.citizen] >= self.min_cost:
                self.eligible.add(t.citizen)
        if t.destination is None or r.random() > 0.55:
            return
        # facility recovery: one material stream per task, never more than was collected
        material = pick(r, MATERIALS[t.material_key])
        method, y_lo, y_hi = METHOD[material]
        centre = t.destination if t.destination.kind == "processing_center" else w.processing_of[t.locality]
        processed_at = t.collected_at + dt.timedelta(hours=5 + r.expovariate(1 / 30))
        if processed_at > w.now_ts:
            return
        input_kg = round(kg * r.uniform(0.55, 0.9), 1)
        recovered = round(max(0.1, min(input_kg, input_kg * r.uniform(y_lo, y_hi))), 1)
        operator = w.operator_for(centre, r.randrange(10))
        verifier = w.operator_for(centre, r.randrange(10) + 1)
        rid = sid(w.seed, "recovery", str(t.id))
        age_days = (w.now_ts - processed_at).days
        if age_days >= 2:
            status = pick(r, [("verified", 72), ("rejected", 10), ("pending", 18)])
        else:
            status = "pending"
        v_at = processed_at + dt.timedelta(hours=6 + r.randrange(0, 40)) if status != "pending" else None
        if v_at is not None and v_at > w.now_ts:
            status, v_at = "pending", None
        out["recovery_records"].append((
            rid, centre.id, self._category_id(material), t.id, None, method, input_kg, recovered, processed_at, operator, status,
            verifier if status != "pending" else None, v_at, "Synthetic demonstration record.", processed_at, v_at or processed_at,
        ))  # fmt: skip
        if status == "verified" and r.random() < 0.65 or status == "pending" and r.random() < 0.3:
            self._passport(t, out, r, centre, rid, material, recovered, processed_at, status, v_at, operator, verifier)
        if status == "verified" and v_at is not None and r.random() < 0.05 and material in LISTING_CATEGORY:
            self._listing(t, out, r, centre, material, recovered, v_at, operator)

    def _category_id(self, code: str) -> str:
        return code  # replaced by the loader with the real material_categories id

    def _passport(self, t: Task, out, r, centre, rid, material, kg, processed_at, rstatus, v_at, operator, verifier) -> None:  # noqa: ANN001
        w = self.w
        assert t.destination is not None and t.collected_at is not None
        pid = sid(w.seed, "passport", str(t.id))
        code = "MP-" + "".join("ABCDEFGHJKLMNPQRSTUVWXYZ23456789"[b % 32] for b in pid.bytes[4:14])
        coll = w.collectors[t.collector]
        events: list[tuple[str, uuid.UUID, dt.datetime, uuid.UUID | None, uuid.UUID | None]] = []
        at = t.collected_at
        events.append(("created", coll, at, None, None))
        events.append(("collected", coll, at + dt.timedelta(minutes=1), None, None))
        unload_at = at + dt.timedelta(hours=2 + r.randrange(0, 4))
        events.append(("transferred", coll, unload_at, None, t.destination.id))
        recv_at = unload_at + dt.timedelta(minutes=20)
        if t.destination.id != centre.id:
            events.append(("transferred", coll, recv_at, None, centre.id))
            recv_at += dt.timedelta(hours=3)
        events.append(("received", operator, recv_at, None, centre.id))
        events.append(("processed", operator, max(processed_at, recv_at + dt.timedelta(minutes=30)), None, centre.id))
        if rstatus == "verified" and v_at is not None:
            events.append(("verified", verifier, max(v_at, events[-1][2] + dt.timedelta(minutes=5)), None, centre.id))
        last_time = events[-1][2]
        if last_time > w.now_ts:
            return
        status = "recovered" if rstatus == "verified" else "in_processing"
        out["material_passports"].append((
            pid, code, self._category_id(material), status, f"Synthetic {material} batch from a demonstration collection",
            kg, t.id, rid, centre.id, operator, events[0][2], last_time,
        ))  # fmt: skip
        for n, (kind, actor, when, frm, to) in enumerate(events, start=1):
            out["custody_events"].append((sid(w.seed, "custody", str(pid), n), pid, n, kind, when, actor, frm, to, None, when, when))

    def _listing(self, t: Task, out, r, centre, material, kg, v_at, operator) -> None:  # noqa: ANN001
        w = self.w
        lid = sid(w.seed, "listing", str(t.id))
        published = v_at + dt.timedelta(hours=20)
        if published > w.now_ts:
            return
        age = (w.now_ts - published).days
        state = pick(r, [("published", 40), ("reserved", 15), ("closed", 45)]) if age > 3 else "published"
        outcome = closed_at = None
        if state == "closed":
            outcome = pick(r, [("handed_over", 60), ("withdrawn", 15), ("expired", 25)])
            closed_at = published + dt.timedelta(days=min(age, 3 + r.randrange(0, 25)))
        expires = published + dt.timedelta(days=30)
        if state == "published" and expires < w.now_ts:
            state, outcome, closed_at = "closed", "expired", expires
        out["marketplace_listings"].append((
            lid, operator, centre.id, f"{LABEL} Recovered {material.replace('_', ' ')}", "Synthetic listing from a demonstration recovery record.",
            LISTING_CATEGORY[material], round(kg, 1), "kg", r.choice(("good", "fair", "good")), "Hyderabad", state, published, closed_at, None,
            expires, None, outcome, published, closed_at or published,
        ))  # fmt: skip
        others = [u for staff in w.operators.values() for u in staff if u != operator]
        if state == "reserved" or (state == "closed" and outcome == "handed_over"):
            wanted = 1
        else:
            wanted = r.randrange(0, 3)
        for j, req in enumerate(r.sample(others, min(wanted, len(others)))):
            rid = sid(w.seed, "request", str(lid), j)
            if state == "reserved" or (state == "closed" and outcome == "handed_over"):
                rs, decided = "accepted", published + dt.timedelta(hours=30)
            elif state == "closed":
                rs, decided = "declined", published + dt.timedelta(hours=30)
            else:
                rs, decided = "pending", None
            out["marketplace_requests"].append((rid, lid, req, "Synthetic request.", rs, decided, published + dt.timedelta(hours=8), decided or published + dt.timedelta(hours=8)))  # fmt: skip

    # ------------------------------------------------------------------ reports that never became tasks
    def _extra_reports(self, d: dt.date, n: int, out: dict[str, list[Row]]) -> None:
        w = self.w
        for k in range(max(1, round(n * 0.22))):
            r = stream(w.seed, "xreport", d.isoformat(), k)
            loc = BY_NAME[w.pick_locality(r.random())]
            lat, lon = round(loc.lat + r.uniform(-0.011, 0.011), 6), round(loc.lon + r.uniform(-0.011, 0.011), 6)
            reported = dt.datetime.combine(d, dt.time(0, 0), tzinfo=IST) + dt.timedelta(minutes=r.randrange(360, 1320))
            if reported > w.now_ts:
                continue
            age = (w.now_ts - reported).days
            options = [("submitted", 35), ("under_review", 25), ("verified", 25), ("rejected", 15)] if age < 7 else [("rejected", 25), ("closed", 45), ("verified", 20), ("under_review", 10)]  # fmt: skip
            status = pick(r, options)
            updated = reported + dt.timedelta(hours=2 + r.randrange(0, 70)) if status != "submitted" else reported
            title = pick(r, [(kind[0], kind[2]) for kind in KINDS])
            out["waste_reports"].append((
                sid(w.seed, "xreport", d.isoformat(), k), w.citizens[int(len(w.citizens) * r.random() ** 1.7)], status, f"{title} at {loc.name}",
                "Synthetic demonstration report (not a real citizen report).", f"{r.choice(STREETS)}, {loc.name}, Hyderabad (synthetic address)",
                round(r.uniform(20, 600), 1), reported, lat, lon, None, None, reported, min(updated, w.now_ts),
            ))  # fmt: skip

    def _incidents(self, d: dt.date, n: int, out: dict[str, list[Row]]) -> None:
        w = self.w
        for k in range(max(1, round(n * 0.10))):
            r = stream(w.seed, "incident", d.isoformat(), k)
            loc = BY_NAME[w.pick_locality(r.random())]
            when = dt.datetime.combine(d, dt.time(0, 0), tzinfo=IST) + dt.timedelta(minutes=r.randrange(360, 1320))
            if when > w.now_ts:
                continue
            age = (w.now_ts - when).days
            options = [("open", 45), ("acknowledged", 30), ("in_progress", 25)] if age < 3 else [("resolved", 70), ("dismissed", 12), ("in_progress", 8), ("acknowledged", 5), ("open", 5)]  # fmt: skip
            status = pick(r, options)
            assigned = w.managers[r.randrange(len(w.managers))] if status != "open" else None
            resolved = when + dt.timedelta(hours=6 + r.randrange(0, 90)) if status in ("resolved", "dismissed") else None
            if resolved is not None and resolved > w.now_ts:
                status, resolved = "in_progress", None
            itype = pick(r, INCIDENT_TYPES)
            out["community_incidents"].append((
                sid(w.seed, "incident", d.isoformat(), k), w.citizens[int(len(w.citizens) * r.random() ** 1.7)], assigned, None, itype, status,
                itype.replace("_", " ").capitalize() + f" near {loc.name}", "Synthetic demonstration incident.",
                f"{r.choice(STREETS)}, {loc.name}, Hyderabad (synthetic address)", resolved,
                "Cleared by the crew (synthetic)" if status == "resolved" else "Not an issue (synthetic)" if status == "dismissed" else None,
                round(loc.lat + r.uniform(-0.011, 0.011), 6), round(loc.lon + r.uniform(-0.011, 0.011), 6), when, resolved or when,
            ))  # fmt: skip

    # ------------------------------------------------------------------ rewards
    def _redemptions(self, d: dt.date, out: dict[str, list[Row]]) -> None:
        w = self.w
        pool = sorted(self.eligible)
        if not pool:
            return
        r = stream(w.seed, "redeem", d.isoformat())
        count = min(len(pool), max(0, round(len(pool) * 0.012)))
        for who in r.sample(pool, count):
            affordable = [it for it in w.item_ids if it[2] <= self.balance[who]]
            if not affordable:
                self.eligible.discard(who)
                continue
            item_id, name, cost = affordable[r.randrange(len(affordable))]
            at = dt.datetime.combine(d, dt.time(0, 0), tzinfo=IST) + dt.timedelta(hours=19, minutes=r.randrange(0, 180))
            redemption = sid(w.seed, "redemption", d.isoformat(), who)
            ledger = sid(w.seed, "ledger", str(redemption), "redeemed")
            user = w.citizens[who]
            out["reward_ledger_entries"].append((ledger, user, "redeemed", -cost, None, "reward_redemption", redemption, None, user, f"Redeemed: {name}", at, at))  # fmt: skip
            self.balance[who] -= cost
            if self.balance[who] < self.min_cost:
                self.eligible.discard(who)
            age = (w.now_ts - at).days
            status = pick(r, [("fulfilled", 70), ("cancelled", 8), ("pending", 22)]) if age > 3 else "pending"
            code = "".join("ABCDEFGHJKMNPQRSTUVWXYZ23456789"[b % 31] for b in redemption.bytes[4:14])
            code = f"{code[:5]}-{code[5:]}"
            fulfilled = cancelled = refund = None
            note = reason = None
            fulfilled_by = cancelled_by = None
            if status == "fulfilled":
                fulfilled, fulfilled_by = at + dt.timedelta(days=1 + r.randrange(0, 3)), w.managers[0]
            elif status == "cancelled":
                cancelled, cancelled_by, reason = at + dt.timedelta(days=1), w.managers[0], "Item out of stock (synthetic)"
                refund = sid(w.seed, "ledger", str(redemption), "refund")
                out["reward_ledger_entries"].append((refund, user, "reversal", cost, None, "reward_redemption", redemption, ledger, w.managers[0], reason, cancelled, cancelled))  # fmt: skip
            out["reward_redemptions"].append((
                redemption, user, item_id, name, cost, code, sid(w.seed, "client", str(redemption)), status, ledger, refund,
                fulfilled_by, fulfilled, note, cancelled_by, cancelled, reason, at, cancelled or fulfilled or at,
            ))  # fmt: skip
