"""Fill a LOCAL throw-away database with clearly labelled demonstration records (developer tooling).

Everything is created through the real API (so every business rule applies) except role grants,
which are written with SQL because no API grants the first administrator. All accounts use
example.org addresses, the report photo is a generated placeholder, and the facilities, vehicles
and Hyderabad addresses are invented. Reference series are imported separately with
`python -m app.cli import-reference-series`.

Use on a fresh database only (it is not idempotent):
  DEMO_PASSWORD=... DEMO_DSN="host=/tmp/pgdev user=postgres dbname=ecomind_demo" python scripts/demo/seed_demo.py
Needs httpx2 (or httpx), psycopg and pillow; `make setup` installs all three. Refuses to run against a non-local API.
"""

import os
import sys

API = os.environ.get("DEMO_API", "http://localhost:8000")
if not API.startswith(("http://localhost", "http://127.0.0.1")):
    sys.exit("Refusing to seed a non-local API")
import datetime as dt
import io

try:  # the backend's dev environment ships `httpx2`; an older environment may have `httpx`
    import httpx2 as httpx
except ImportError:
    import httpx
import psycopg
from PIL import Image, ImageDraw

B = API + "/api/v1"
PW = os.environ["DEMO_PASSWORD"]


def reg(email, name):
    r = httpx.post(f"{B}/auth/register", json={"email": email, "password": PW, "full_name": name})
    if r.status_code not in (201, 409):
        print("reg", r.status_code, r.text)
        sys.exit(1)


people = {
    "admin": ("admin@example.org", "Priya Admin", "administrator"),
    "manager": ("manager@example.org", "Meera Manager", "manager"),
    "collector": ("collector@example.org", "Ravi Collector", "collector"),
    "operator": ("operator@example.org", "Omar Operator", "facility_operator"),
    "citizen": ("citizen@example.org", "Asha Citizen", None),
    "verifier": ("verifier@example.org", "Vera Verifier", "facility_operator"),
}
for k, (e, n, _) in people.items():
    reg(e, n)
c = psycopg.connect(os.environ["DEMO_DSN"], autocommit=True)
for k, (e, n, role) in people.items():
    if role:
        c.execute(
            "insert into user_roles(user_id,role_id) select u.id,r.id from users u, roles r where u.email=%s and r.name=%s on conflict do nothing",
            (e, role),
        )
tok = {}
for k, (e, n, _) in people.items():
    r = httpx.post(f"{B}/auth/login", json={"email": e, "password": PW})
    r.raise_for_status()
    tok[k] = r.json()["access_token"]


def H(k):
    return {"Authorization": "Bearer " + tok[k]}


def call(k, m, p, **kw):
    r = httpx.request(m, B + p, headers=H(k), timeout=30, **kw)
    if r.status_code >= 400:
        print("ERR", k, m, p, r.status_code, r.text[:300])
        return None
    return r.json() if r.content else None


dep = call(
    "manager",
    "POST",
    "/facilities",
    json={
        "code": "HYD-DEP1",
        "name": "Kukatpally Depot",
        "facility_type": "depot",
        "city": "Hyderabad",
        "region": "Telangana",
        "country_code": "IN",
        "latitude": "17.4948",
        "longitude": "78.3996",
        "daily_capacity_kg": "20000",
    },
)
mrf = call(
    "manager",
    "POST",
    "/facilities",
    json={
        "code": "HYD-MRF1",
        "name": "Jeedimetla Processing Centre",
        "facility_type": "processing_center",
        "city": "Hyderabad",
        "region": "Telangana",
        "country_code": "IN",
        "latitude": "17.5110",
        "longitude": "78.4560",
        "daily_capacity_kg": "60000",
    },
)
call(
    "manager",
    "POST",
    "/facilities",
    json={
        "code": "HYD-DROP1",
        "name": "Gachibowli Drop-off Point",
        "facility_type": "drop_off_point",
        "city": "Hyderabad",
        "country_code": "IN",
        "latitude": "17.4401",
        "longitude": "78.3489",
        "status": "maintenance",
    },
)
v1 = call(
    "manager",
    "POST",
    "/fleet/vehicles",
    json={
        "registration_number": "TS09-UA-1234",
        "vehicle_type": "compactor_truck",
        "capacity_kg": "6000",
        "home_facility_id": dep["id"],
    },
)
call(
    "manager",
    "POST",
    "/fleet/vehicles",
    json={
        "registration_number": "TS09-UB-5678",
        "vehicle_type": "van",
        "capacity_kg": "900",
        "home_facility_id": dep["id"],
    },
)
call(
    "manager",
    "POST",
    "/fleet/vehicles",
    json={
        "registration_number": "TS09-UC-0042",
        "vehicle_type": "cargo_bike",
        "capacity_kg": "120",
        "status": "maintenance",
    },
)
img = Image.new("RGB", (640, 480), (70, 110, 90))
d = ImageDraw.Draw(img)
d.rectangle([40, 40, 600, 440], outline=(255, 255, 255), width=4)
d.text((60, 200), "DEMO PLACEHOLDER IMAGE (not a real photo)", fill=(255, 255, 255))
buf = io.BytesIO()
img.save(buf, "JPEG")
m = httpx.post(
    f"{B}/waste-reports/media?filename=demo.jpg",
    headers={**H("citizen"), "Content-Type": "image/jpeg"},
    content=buf.getvalue(),
)
m.raise_for_status()
mid = m.json()["id"]
reports = []
for i, (t, a, w, lat, lon) in enumerate(
    [
        ("Overflowing skip behind market", "Begum Bazaar Road", "120", "17.3616", "78.4747"),
        ("Garden waste pile on corner", "Road No. 12, Banjara Hills", "60", "17.4126", "78.4482"),
        ("Mixed rubble near school", "Kondapur Main Road", "300", "17.4600", "78.3570"),
        ("Bags left at bus stop", "Ameerpet Junction", "25", "17.4375", "78.4483"),
    ]
):
    r = call(
        "citizen",
        "POST",
        "/waste-reports",
        json={
            "title": t,
            "address_text": a,
            "estimated_weight_kg": w,
            "latitude": lat,
            "longitude": lon,
            "media_ids": [mid] if i == 0 else [],
        },
    )
    reports.append(r)
for r in reports[:3]:
    call("manager", "POST", f"/waste-reports/{r['id']}/review", json={"status": "verified"})
call(
    "manager", "POST", f"/waste-reports/{reports[3]['id']}/review", json={"status": "under_review"}
)
users = call("manager", "GET", "/admin/users", params={"role": "collector"})["items"]
col = users[0]
due = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).isoformat()
tasks = []
for r, pr in zip(reports[:3], ("high", "normal", "urgent")):
    tasks.append(
        call(
            "manager",
            "POST",
            "/collection/tasks",
            json={
                "waste_report_id": r["id"],
                "priority": pr,
                "due_at": due,
                "destination_facility_id": mrf["id"],
            },
        )
    )
call(
    "manager",
    "POST",
    "/collection/tasks",
    json={
        "title": "Scheduled pickup, Secunderabad station",
        "address_text": "Secunderabad Railway Station",
        "latitude": "17.4337",
        "longitude": "78.5013",
        "priority": "low",
    },
)
for t in tasks[:2]:
    call(
        "manager",
        "POST",
        f"/collection/tasks/{t['id']}/assign",
        json={"assignee_id": col["id"], "vehicle_id": v1["id"]},
    )
call("collector", "POST", f"/collection/tasks/{tasks[0]['id']}/start")
call(
    "collector",
    "POST",
    f"/collection/tasks/{tasks[0]['id']}/events",
    json={"event_type": "arrived"},
)
call(
    "collector",
    "POST",
    f"/collection/tasks/{tasks[0]['id']}/complete",
    json={"collected_weight_kg": "118.500", "destination_facility_id": mrf["id"]},
)
call("collector", "POST", f"/collection/tasks/{tasks[1]['id']}/start")
cats = call("manager", "GET", "/sorting-guide/categories")["items"]
cm = {x["code"]: x for x in cats}
print("categories", list(cm))
call(
    "operator",
    "POST",
    "/circular-economy/recovery-records",
    json={
        "facility_id": mrf["id"],
        "material_category_id": cm["plastic"]["id"],
        "recovery_method": "recycled",
        "input_weight_kg": "80",
        "recovered_weight_kg": "62.5",
        "processed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    },
)
rec = call(
    "operator",
    "POST",
    "/circular-economy/recovery-records",
    json={
        "facility_id": mrf["id"],
        "material_category_id": cm["glass"]["id"],
        "recovery_method": "recycled",
        "input_weight_kg": "40",
        "recovered_weight_kg": "36",
        "processed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
    },
)
call(
    "manager",
    "POST",
    f"/circular-economy/recovery-records/{rec['id']}/verify",
    json={"decision": "verified"},
)
p = call(
    "operator",
    "POST",
    "/material-passports",
    json={
        "material_category_id": cm["glass"]["id"],
        "weight_kg": "36",
        "description": "Glass cullet batch (demo)",
        "current_facility_id": mrf["id"],
    },
)
if p:
    for e in ({"event_type": "received", "to_facility_id": mrf["id"]}, {"event_type": "processed"}):
        call("operator", "POST", f"/material-passports/{p['id']}/events", json=e)
    call(
        "operator",
        "POST",
        f"/material-passports/{p['id']}/recovery",
        json={"recovery_record_id": rec["id"]},
    )
    call(
        "operator", "POST", f"/material-passports/{p['id']}/events", json={"event_type": "verified"}
    )
call(
    "manager",
    "POST",
    "/sorting-guide/guidance",
    json={
        "material_category_id": cm["glass"]["id"],
        "disposal_method": "recycle",
        "title": "Rinse glass containers (demo entry)",
        "instructions": "Empty and rinse bottles and jars; remove metal lids. This is demonstration text, not a local rule.",
        "source_reference": None,
    },
)
call(
    "manager",
    "POST",
    "/sorting-guide/guidance",
    json={
        "material_category_id": cm["paper"]["id"],
        "disposal_method": "recycle",
        "title": "Keep paper dry (demo entry)",
        "instructions": "Wet or greasy paper is usually not recyclable. Demonstration text, not a local rule.",
        "source_reference": "Demo seed: no real source",
    },
)
for t, ty in (
    ("Dumped sofa on Lake Road", "illegal_dumping"),
    ("Bin overflowing at park gate", "overflowing_bin"),
    ("Burning of leaves behind clinic", "open_burning"),
):
    call(
        "citizen",
        "POST",
        "/community-incidents",
        json={"incident_type": ty, "title": t, "address_text": "Hyderabad"},
    )
inc = call("manager", "GET", "/community-incidents")["items"]
call(
    "manager",
    "POST",
    f"/community-incidents/{inc[-1]['id']}/status",
    json={"status": "acknowledged"},
)
call(
    "manager",
    "POST",
    "/route-planning/plans",
    json={
        "name": "Tuesday north loop",
        "planned_date": (dt.date.today() + dt.timedelta(days=1)).isoformat(),
        "start_facility_id": dep["id"],
        "end_facility_id": mrf["id"],
        "task_ids": [tasks[2]["id"]],
        "vehicle_id": v1["id"],
    },
)
call(
    "manager",
    "POST",
    "/rewards/adjustments",
    json={
        "user_id": reports[0]["reporter_id"],
        "points": 25,
        "description": "Community clean-up participation (demo)",
    },
)

for series in ("reference:austin", "reference:ballarat"):
    call(
        "manager",
        "POST",
        "/forecasting/forecasts",
        json={"series": series, "horizon_weeks": 8, "save": True},
    )
    call("manager", "POST", "/anomalies/scan", json={"series": series, "lookback_weeks": 104})
print("seeded")
