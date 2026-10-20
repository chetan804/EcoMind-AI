#!/usr/bin/env python3
"""Generate docs/database/er-diagram.md (a Mermaid entity-relationship diagram) from the metadata.

    python scripts/database/generate_er_diagram.py          # rewrite
    python scripts/database/generate_er_diagram.py --check  # CI: fail if stale

Foreign keys in the SQLAlchemy metadata are the single source of truth, so the diagram cannot drift
from the schema. Entities show only key columns; every column is in data-dictionary.md.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/database/er-diagram.md"
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost/x")
os.environ.setdefault("SECRET_KEY", "diagram-generation-only-secret-0123456789")

from app.db.base import Base  # noqa: E402
from app.db.metadata import target_metadata  # noqa: E402


def owners() -> dict[str, str]:
    return {m.local_table.name: m.class_.__module__.split(".")[2] for m in Base.registry.mappers}


def render() -> str:
    owner = owners()
    tables = sorted(target_metadata.tables.values(), key=lambda t: t.name)
    lines = [
        "# Entity-relationship diagram",
        "",
        "> **Generated** by `scripts/database/generate_er_diagram.py` from the SQLAlchemy models. "
        "Do not edit by hand; CI fails if this file is stale.",
        "",
        "Entities show their primary and foreign key columns only; the full column list, constraints and "
        "owning module of every table are in [data-dictionary.md](data-dictionary.md). A relationship line "
        "means a foreign key: the parent side is `||` (exactly one) or `|o` (a nullable foreign key means the "
        "parent is optional); the child side is `o{` (zero or more).",
        "",
        "```mermaid",
        "erDiagram",
    ]
    edges: list[str] = []
    for table in tables:
        fk_cols = {c.name for fk in table.foreign_key_constraints for c in fk.columns}
        for fk in sorted(table.foreign_key_constraints, key=lambda f: f.name or ""):
            column = fk.columns[0]
            parent = fk.referred_table.name
            left = "|o" if column.nullable else "||"
            edges.append(f'    {parent} {left}--o{{ {table.name} : "{column.name}"')
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            if col.primary_key or col.name in fk_cols:
                tag = "PK" if col.primary_key else "FK"
                if col.primary_key and col.name in fk_cols:
                    tag = "PK, FK"
                lines.append(f"        {'uuid' if 'UUID' in str(col.type).upper() else 'string'} {col.name} {tag}")
        lines.append("    }")
    lines += edges
    lines += ["```", "", "## Tables by owning module", ""]
    by_module: dict[str, list[str]] = {}
    for table in tables:
        by_module.setdefault(owner.get(table.name, "association (no model class)"), []).append(table.name)
    for module in sorted(by_module):
        lines.append(f"- **{module}**: " + ", ".join(f"`{t}`" for t in by_module[module]))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if not OUTPUT.exists() or OUTPUT.read_text() != content:
            print(f"{OUTPUT.relative_to(ROOT)} is stale: run scripts/database/generate_er_diagram.py")
            return 1
        print("er-diagram.md is up to date")
        return 0
    OUTPUT.write_text(content)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
