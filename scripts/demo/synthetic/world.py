"""The fixed part of the synthetic city: zones, facilities, fleet, people, reward catalogue.

Everything is a pure function of (seed, profile), so building it twice gives identical rows.
"""

from __future__ import annotations

import bisect
import datetime as dt
import secrets
import uuid
from dataclasses import dataclass, field

from .geography import (
    BY_NAME, DEPOTS, DROP_OFF_LOCALITIES, LOCALITIES, PROCESSING, TRANSFER, haversine_km,
)  # fmt: skip
from .ids import sid, stream
from .profiles import Profile

IST = dt.timezone(dt.timedelta(hours=5, minutes=30), "Asia/Kolkata")
EMAIL_DOMAIN = "synthetic.example.org"  # a subdomain of the reserved example.org
LABEL = "[Demo]"
VEHICLE_TYPES = (  # (type, capacity kg, share of the fleet in percent)
    ("compactor_truck", 6000, 35), ("tipper_truck", 3500, 25), ("van", 900, 35), ("cargo_bike", 120, 5),
)  # fmt: skip
REWARD_ITEMS = (
    ("Reusable cloth bag", 500), ("Compost starter kit", 1000), ("Steel water bottle", 1500),
    ("Community garden voucher", 2500), ("Seed packet bundle", 800), ("Recycled-paper notebook set", 1200),
    ("Neighbourhood clean-up kit", 4000), ("Plant sapling", 600),
)  # fmt: skip
FIRST = (
    "Aarav Aditya Akhil Anjali Ananya Arjun Bhavana Charan Deepika Divya Farhan Fatima Gayatri Harsha "
    "Imran Ishaan Jahnavi Karthik Kavya Lakshmi Madhavi Manoj Meera Mohan Nandini Naveen Nikhil Pooja "
    "Pranav Priya Rahul Rajesh Ramya Ravi Rohit Sadia Sai Sandeep Sangeetha Shreya Sneha Srinivas "
    "Suresh Swathi Tanvi Uday Vamsi Varun Vijay Yamini Zoya"
).split()  # fmt: skip
LAST = (
    "Reddy Rao Naidu Sharma Verma Khan Siddiqui Ali Begum Goud Yadav Chowdary Varma Patel Gupta Iyer "
    "Menon Nair Pillai Kumar Singh Das Mishra Joshi Kulkarni Shaik Mohammed Hussain Qureshi Rajulu "
    "Prasad Murthy Sastry Raju Babu Devi"
).split()  # fmt: skip


def full_name(seed: int, kind: str, i: int) -> str:
    r = stream(seed, "name", kind, i)
    return f"{r.choice(FIRST)} {r.choice(LAST)} (demo)"


@dataclass(frozen=True)
class Facility:
    id: uuid.UUID
    code: str
    name: str
    kind: str
    lat: float
    lon: float
    locality: str
    status: str = "active"


@dataclass
class World:
    seed: int
    profile: Profile
    anchor: dt.date
    zone_ids: dict[str, uuid.UUID] = field(default_factory=dict)
    facilities: list[Facility] = field(default_factory=list)
    depot_of: dict[str, Facility] = field(default_factory=dict)  # locality -> nearest depot
    processing_of: dict[str, Facility] = field(default_factory=dict)  # locality -> nearest centre
    transfer_of: dict[str, Facility] = field(default_factory=dict)
    managers: list[uuid.UUID] = field(default_factory=list)
    collectors: list[uuid.UUID] = field(default_factory=list)
    collector_vehicle: list[int] = field(default_factory=list)
    collector_depot: list[Facility] = field(default_factory=list)
    pools: dict[str, list[int]] = field(default_factory=dict)  # depot code -> collector indexes
    vehicles: list[tuple[uuid.UUID, str, int, str, Facility]] = field(default_factory=list)
    operators: dict[str, list[uuid.UUID]] = field(default_factory=dict)  # facility code -> staff
    citizens: list[uuid.UUID] = field(default_factory=list)
    item_ids: list[tuple[uuid.UUID, str, int]] = field(default_factory=list)
    weights_cum: list[float] = field(default_factory=list)
    marker: str = ""

    # ------------------------------------------------------------------ construction
    @classmethod
    def build(cls, seed: int, profile: Profile, anchor: dt.date) -> World:
        w = cls(seed, profile, anchor)
        w.marker = (
            f"Synthetic demonstration dataset (not official data). seed={seed} "
            f"profile={profile.name} anchor={anchor.isoformat()}"
        )
        for loc in LOCALITIES:
            w.zone_ids[loc.name] = sid(seed, "zone", loc.name)
        for table, kind in ((DEPOTS, "depot"), (PROCESSING, "processing_center"), (TRANSFER, "transfer_station")):
            for code, name, locality in table:
                loc = BY_NAME[locality]
                w.facilities.append(
                    Facility(sid(seed, "facility", code), f"SYN-{code}", f"{LABEL} {name}", kind,
                             round(loc.lat + 0.004, 6), round(loc.lon + 0.004, 6), locality)
                )  # fmt: skip
        for i, locality in enumerate(DROP_OFF_LOCALITIES[: profile.drop_offs]):
            loc = BY_NAME[locality]
            status = "maintenance" if i == 3 else "active"
            code = f"DO-{i + 1:02d}"
            w.facilities.append(
                Facility(sid(seed, "facility", code), f"SYN-{code}", f"{LABEL} {locality} Drop-off Point",
                         "drop_off_point", round(loc.lat - 0.003, 6), round(loc.lon - 0.002, 6), locality, status)
            )  # fmt: skip
        for loc in LOCALITIES:
            for store, kind in ((w.depot_of, "depot"), (w.processing_of, "processing_center"), (w.transfer_of, "transfer_station")):
                store[loc.name] = min(
                    (f for f in w.facilities if f.kind == kind),
                    key=lambda f, loc=loc: haversine_km(loc.lat, loc.lon, f.lat, f.lon),
                )  # fmt: skip
        w.managers = [sid(seed, "user", "manager", i) for i in range(profile.managers)]
        depots = [f for f in w.facilities if f.kind == "depot"]
        total = 0.0
        for loc in LOCALITIES:
            total += loc.weight
            w.weights_cum.append(total)
        for i in range(profile.collectors):
            w.collectors.append(sid(seed, "user", "collector", i))
            depot = depots[i % len(depots)]
            w.collector_depot.append(depot)
            w.collector_vehicle.append(i)
            kind, cap, _ = cls._vehicle_type(i)
            status = "maintenance" if i % 25 == 24 else "retired" if i % 41 == 40 else "available"
            w.vehicles.append((sid(seed, "vehicle", i), kind, cap, status, depot))
            if status == "available":
                w.pools.setdefault(depot.code, []).append(i)
        for f in w.facilities:
            if f.kind in ("depot", "processing_center", "transfer_station"):
                w.operators[f.code] = [sid(seed, "user", "operator", f.code, j) for j in range(profile.operators_per_site)]
        w.citizens = [sid(seed, "user", "citizen", i) for i in range(profile.citizens)]
        for i, (name, cost) in enumerate(REWARD_ITEMS):
            w.item_ids.append((sid(seed, "reward_item", i), f"{LABEL} {name}", cost))
        return w

    @staticmethod
    def _vehicle_type(i: int) -> tuple[str, int, int]:
        slot = (i * 7) % 100
        acc = 0
        for kind, cap, share in VEHICLE_TYPES:
            acc += share
            if slot < acc:
                return kind, cap, share
        return VEHICLE_TYPES[-1]

    # ------------------------------------------------------------------ helpers
    def pick_locality(self, u: float) -> str:
        idx = bisect.bisect_left(self.weights_cum, u * self.weights_cum[-1])
        return LOCALITIES[min(idx, len(LOCALITIES) - 1)].name

    def operator_for(self, facility: Facility, r_index: int) -> uuid.UUID:
        staff = self.operators.get(facility.code) or next(iter(self.operators.values()))
        return staff[r_index % len(staff)]

    @property
    def now_ts(self) -> dt.datetime:
        """Data ends here: 06:00 IST on the anchor date. Later work is planned, not done."""
        return dt.datetime.combine(self.anchor, dt.time(6, 0), tzinfo=IST)

    # ------------------------------------------------------------------ rows for dimension tables
    def password_hash(self) -> str:
        """A valid Argon2id hash of a random secret that is thrown away: these accounts cannot sign in."""
        from argon2 import PasswordHasher  # installed with the backend

        return PasswordHasher().hash(secrets.token_urlsafe(32))

    def zone_rows(self) -> list[tuple[object, ...]]:
        t0 = self.now_ts - dt.timedelta(days=self.profile.days + 30)
        return [
            (self.zone_ids[loc.name], f"SYN-ZN-{i + 1:02d}", f"{LABEL} {loc.name}", loc.zone_type,
             f"{self.marker}. Approximate locality area, not an official ward.", True, t0, t0)
            for i, loc in enumerate(LOCALITIES)
        ]  # fmt: skip

    def facility_rows(self) -> list[tuple[object, ...]]:
        t0 = self.now_ts - dt.timedelta(days=self.profile.days + 20)
        caps = {"depot": 25000, "processing_center": 80000, "transfer_station": 40000, "drop_off_point": 3000}
        return [
            (f.id, f.code, f.name, f.kind, f.status, f"Synthetic address, {f.locality} (not a real site)",
             "Hyderabad", "Telangana", "IN", caps[f.kind], None, f.lat, f.lon, self.zone_ids[f.locality], t0, t0)
            for f in self.facilities
        ]  # fmt: skip

    def vehicle_rows(self) -> list[tuple[object, ...]]:
        t0 = self.now_ts - dt.timedelta(days=self.profile.days + 10)
        return [
            (vid, f"TS09-SYN-{i + 1:04d}", kind, status, cap, depot.id, t0, t0)
            for i, (vid, kind, cap, status, depot) in enumerate(self.vehicles)
        ]  # fmt: skip

    def user_rows(self, pw_hash: str) -> tuple[list[tuple[object, ...]], list[tuple[uuid.UUID, str]]]:
        """(users rows, (user id, role name) rows)."""
        t_staff = self.now_ts - dt.timedelta(days=self.profile.days + 15)
        users: list[tuple[object, ...]] = []
        roles: list[tuple[uuid.UUID, str]] = []

        def add(uid: uuid.UUID, email: str, name: str, role: str, created: dt.datetime) -> None:
            users.append((uid, email, pw_hash, name, True, None, created, created, created))
            roles.append((uid, role))

        for i, uid in enumerate(self.managers):
            add(uid, f"manager{i + 1:04d}@{EMAIL_DOMAIN}", full_name(self.seed, "manager", i), "manager", t_staff)
        for i, uid in enumerate(self.collectors):
            add(uid, f"collector{i + 1:04d}@{EMAIL_DOMAIN}", full_name(self.seed, "collector", i), "collector", t_staff)
        for code, staff in self.operators.items():
            for j, uid in enumerate(staff):
                add(uid, f"operator-{code.lower()}-{j + 1}@{EMAIL_DOMAIN}", full_name(self.seed, "operator", f"{code}{j}"), "facility_operator", t_staff)  # fmt: skip
        span = max(1, self.profile.days)
        for i, uid in enumerate(self.citizens):
            r = stream(self.seed, "citizen", i)
            created = self.now_ts - dt.timedelta(days=self.profile.days + 10) + dt.timedelta(
                days=r.random() ** 1.4 * span * 0.8
            )  # accounts appear steadily, most early
            add(uid, f"citizen{i + 1:06d}@{EMAIL_DOMAIN}", full_name(self.seed, "citizen", i), "citizen", created)
        return users, roles

    def reward_item_rows(self) -> list[tuple[object, ...]]:
        t0 = self.now_ts - dt.timedelta(days=self.profile.days + 5)
        return [
            (iid, name, "Synthetic catalogue entry for demonstrations.", cost, None, 3, True, None,
             self.managers[0], t0, t0)
            for iid, name, cost in self.item_ids
        ]  # fmt: skip
