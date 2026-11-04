#!/usr/bin/env python3
"""Export the role -> permission catalog for the frontend role-home tests.

The backend catalog (``backend/app/modules/users/rbac.py``) is the single source of truth. The
frontend tests read ``frontend/tests/fixtures/role-permissions.json`` so they exercise each role
with the permissions the server really grants, instead of a hand-copied list that can drift.

    python scripts/quality/export_role_permissions.py          # write the file
    python scripts/quality/export_role_permissions.py --check  # exit 1 if it is out of date
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RBAC = ROOT / "backend" / "app" / "modules" / "users" / "rbac.py"
TARGET = ROOT / "frontend" / "tests" / "fixtures" / "role-permissions.json"


def render() -> str:
    spec = importlib.util.spec_from_file_location("ecomind_rbac", RBAC)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass/typing helpers expect the module to be registered
    spec.loader.exec_module(module)
    roles = {name: sorted(perms) for name, (_description, perms) in module.ROLES.items()}
    return json.dumps(roles, indent=2, sort_keys=True) + "\n"


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != content:
            print(f"{TARGET.relative_to(ROOT)} is out of date; run this script without --check.")
            return 1
        print("role-permissions.json is up to date")
        return 0
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(content, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
