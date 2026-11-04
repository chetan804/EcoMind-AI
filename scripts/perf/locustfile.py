"""Locust scenario: the read traffic the screens actually generate, per role (developer tooling).

    cd scripts/perf
    LOAD_PASSWORD='...' /path/to/locust -f locustfile.py --headless -u 25 -r 5 -t 60s \
        --host http://localhost:8000 --csv /tmp/locust-25 --only-summary

Read-only: the only POSTs are one sign-in per account at the start of the run (tokens are shared by
the virtual users, so the per-e-mail sign-in lockout is not exercised). Refuses non-local hosts
unless LOAD_ALLOW_REMOTE=1. Users are weighted roughly like a real day: mostly citizens, some
collectors and operators, few managers. The numbers describe the machine, the data volume and the
process layout they were taken on; they are not a capacity claim for any deployment.
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

from locust import HttpUser, between, events, task

ACCOUNTS = {
    "citizen": os.environ.get("LOAD_CITIZEN", "citizen@example.org"),
    "collector": os.environ.get("LOAD_COLLECTOR", "collector@example.org"),
    "operator": os.environ.get("LOAD_OPERATOR", "operator@example.org"),
    "manager": os.environ.get("LOAD_MANAGER", "manager@example.org"),
}
TOKENS: dict[str, str] = {}
API = "/api/v1"


@events.test_start.add_listener
def sign_in(environment, **_kwargs):  # type: ignore[no-untyped-def]
    host = urlparse(environment.host or "")
    if host.hostname not in {"localhost", "127.0.0.1", "::1"} and os.environ.get("LOAD_ALLOW_REMOTE") != "1":
        print("Refusing a non-local host (set LOAD_ALLOW_REMOTE=1 only for a system you run)", file=sys.stderr)
        environment.process_exit_code = 2
        environment.runner.quit()
        return
    import httpx

    password = os.environ["LOAD_PASSWORD"]
    for role, email in ACCOUNTS.items():
        r = httpx.post(f"{environment.host}{API}/auth/login", json={"email": email, "password": password}, timeout=30)
        r.raise_for_status()
        TOKENS[role] = r.json()["access_token"]


class Member(HttpUser):
    abstract = True
    wait_time = between(1, 3)  # think time, as a person reading a screen
    role = "citizen"

    def get(self, path: str, name: str | None = None) -> None:
        self.client.get(f"{API}{path}", headers={"Authorization": f"Bearer {TOKENS[self.role]}"}, name=name or path)


class Citizen(Member):
    weight = 6
    role = "citizen"

    @task(5)
    def my_reports(self) -> None:
        self.get("/waste-reports?mine=true&page=1&page_size=20", "/waste-reports?mine (page)")

    @task(4)
    def notifications(self) -> None:
        self.get("/notifications/unread-count")

    @task(2)
    def rewards(self) -> None:
        self.get("/rewards/catalog")

    @task(2)
    def marketplace(self) -> None:
        self.get("/marketplace/listings?page=1&page_size=20", "/marketplace/listings (page)")

    @task(1)
    def help_articles(self) -> None:
        self.get("/support/articles?page=1&page_size=20", "/support/articles (page)")


class Collector(Member):
    weight = 2
    role = "collector"

    @task(5)
    def my_tasks(self) -> None:
        self.get("/collection/tasks?mine=true&page=1&page_size=20", "/collection/tasks?mine (page)")

    @task(3)
    def notifications(self) -> None:
        self.get("/notifications/unread-count")

    @task(1)
    def routes(self) -> None:
        self.get("/route-planning/plans?page=1&page_size=20", "/route-planning/plans (page)")


class Operator(Member):
    weight = 1
    role = "operator"

    @task(4)
    def recovery(self) -> None:
        self.get("/circular-economy/recovery-records?page=1&page_size=20", "/circular-economy/recovery-records (page)")

    @task(3)
    def passports(self) -> None:
        self.get("/material-passports?page=1&page_size=20", "/material-passports (page)")

    @task(2)
    def notifications(self) -> None:
        self.get("/notifications/unread-count")


class Manager(Member):
    weight = 1
    role = "manager"

    @task(4)
    def overview(self) -> None:
        self.get("/analytics/overview?days=30")

    @task(2)
    def weekly_trend(self) -> None:
        self.get("/analytics/weekly-trend?weeks=12")

    @task(4)
    def reports(self) -> None:
        self.get("/waste-reports?page=1&page_size=20", "/waste-reports (page)")

    @task(3)
    def tasks(self) -> None:
        self.get("/collection/tasks?page=1&page_size=20", "/collection/tasks (page)")

    @task(2)
    def facilities(self) -> None:
        self.get("/facilities?page=1&page_size=20", "/facilities (page)")

    @task(2)
    def fleet(self) -> None:
        self.get("/fleet/vehicles?page=1&page_size=20", "/fleet/vehicles (page)")

    @task(2)
    def incidents(self) -> None:
        self.get("/community-incidents?page=1&page_size=20", "/community-incidents (page)")

    @task(1)
    def alerts(self) -> None:
        self.get("/anomalies?page=1&page_size=20", "/anomalies (page)")
