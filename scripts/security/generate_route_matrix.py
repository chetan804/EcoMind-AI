#!/usr/bin/env python3
"""Generate docs/security/route-permission-matrix.md: every API route and who may call it.

    python scripts/security/generate_route_matrix.py          # rewrite
    python scripts/security/generate_route_matrix.py --check  # CI: fail if stale

The routes come from the mounted FastAPI app (``app.common.route_inventory``) and the roles from the
RBAC catalog, so the matrix cannot drift from the code.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/security/route-permission-matrix.md"
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost/x")
os.environ.setdefault("SECRET_KEY", "route-matrix-generation-only-secret-0123456789")

from app.common.route_inventory import RouteInfo, inventory  # noqa: E402
from app.main import create_app  # noqa: E402
from app.modules.users.rbac import ROLES  # noqa: E402

ROLE_ORDER = ["citizen", "collector", "facility_operator", "manager", "administrator"]


def holders(info: RouteInfo) -> str:
    if not info.requires_sign_in:
        return "anyone"
    held = {name: perms for name, (_, perms) in ROLES.items()}
    if not info.permissions:
        return "any signed-in user"
    check = any if info.any_of else all
    names = [r for r in ROLE_ORDER if r in held and check(p in held[r] for p in info.permissions)]
    return ", ".join(names) if names else "no role"


def access(info: RouteInfo) -> str:
    if not info.requires_sign_in:
        return "public" + (" (cookie + CSRF header)" if info.requires_csrf_header else "")
    if not info.permissions:
        return "signed in"
    joiner = " or " if info.any_of else " and "
    return joiner.join(f"`{p}`" for p in info.permissions)


def render() -> str:
    routes = inventory(create_app())
    lines = [
        "# Route permission matrix",
        "",
        "> **Generated** by `scripts/security/generate_route_matrix.py` from the mounted application and the "
        "RBAC catalog (`backend/app/modules/users/rbac.py`). Do not edit by hand; CI fails if this file is "
        "stale. `backend/tests/security/test_route_inventory.py` fails if a route becomes public or "
        "signed-in-only without being listed there.",
        "",
        f"{len(routes)} operations. Authorization is decided on the server from the database on every "
        "request; hiding a button in the UI is only a convenience. Object-level rules (for example a citizen "
        "reading only their own reports) are enforced inside the services and covered by the module tests.",
        "",
        "| Method | Path | Access | Roles that hold it |",
        "|---|---|---|---|",
    ]
    for r in routes:
        lines.append(f"| {r.method} | `{r.path}` | {access(r)} | {holders(r)} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if not OUTPUT.exists() or OUTPUT.read_text() != content:
            print(f"{OUTPUT.relative_to(ROOT)} is stale: run scripts/security/generate_route_matrix.py")
            return 1
        print("route-permission-matrix.md is up to date")
        return 0
    OUTPUT.write_text(content)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
