#!/usr/bin/env python3
"""Generate docs/database/data-dictionary.md from the SQLAlchemy metadata.

    backend/.venv/bin/python scripts/database/generate_data_dictionary.py          # rewrite
    backend/.venv/bin/python scripts/database/generate_data_dictionary.py --check  # CI: fail if stale

The metadata is the single source of truth, so the dictionary cannot drift from the schema.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "docs/database/data-dictionary.md"
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://x:x@localhost/x")
os.environ.setdefault("SECRET_KEY", "dictionary-generation-only-secret-0123456789")

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint  # noqa: E402
from sqlalchemy.sql.elements import TextClause  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.metadata import target_metadata  # noqa: E402


def type_name(column: Any) -> str:
    if type(column.type).__name__ == "DateTime":
        return "timestamptz" if column.type.timezone else "timestamp"
    return str(column.type).lower()


def owner_and_summary() -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        table = mapper.local_table.name
        module = cls.__module__.split(".")[2]
        summary = (cls.__doc__ or "").strip().split("\n\n")[0].replace("\n", " ")
        result[table] = (module, summary)
    return result


def render() -> str:
    owners = owner_and_summary()
    lines = [
        "# Data dictionary",
        "",
        "> **Generated** by `scripts/database/generate_data_dictionary.py` from the SQLAlchemy models. "
        "Do not edit by hand; run `make data-dictionary`. CI fails if this file is stale.",
        "",
        "Conventions are described in [schema-overview.md](schema-overview.md). `PK` primary key, "
        "`FK` foreign key, `UQ` unique, `NN` not null. Quantity units are part of the column name "
        "(`*_kg`, `*_km`, `*_min`, `*_bytes`, `*_px`) or an explicit `unit` column.",
        "",
    ]
    by_module: dict[str, list[str]] = {}
    for table in target_metadata.sorted_tables:
        by_module.setdefault(owners[table.name][0], []).append(table.name)
    for module in sorted(by_module):
        lines += [f"## Module `{module}`", ""]
        for name in sorted(by_module[module]):
            table = target_metadata.tables[name]
            summary = owners[name][1]
            lines += [f"### `{name}`", ""]
            if summary:
                lines += [summary, ""]
            lines += ["| Column | Type | Null | Default | Notes |", "|---|---|---|---|---|"]
            fks = {
                col.name: f"FK -> `{fk.column.table.name}.{fk.column.name}`"
                + (f" ON DELETE {fk.ondelete}" if fk.ondelete else "")
                for constraint in table.constraints
                if isinstance(constraint, ForeignKeyConstraint)
                for col, fk in zip(constraint.columns, constraint.elements, strict=True)
            }
            for column in table.columns:
                notes = []
                if column.primary_key:
                    notes.append("PK")
                if column.name in fks:
                    notes.append(fks[column.name])
                if column.unique:
                    notes.append("UQ")
                default = ""
                if column.server_default is not None:
                    default = f"`{getattr(column.server_default.arg, 'text', column.server_default.arg)}`"
                lines.append(
                    f"| `{column.name}` | {type_name(column)} | "
                    f"{'NN' if not column.nullable else 'null'} | {default} | {'; '.join(notes)} |"
                )
            constraints = []
            for c in sorted(table.constraints, key=lambda c: str(c.name)):
                if isinstance(c, CheckConstraint) and not str(c.name).endswith("_valid"):
                    text = c.sqltext.text if isinstance(c.sqltext, TextClause) else str(c.sqltext)
                    constraints.append(f"- `{c.name}`: `{' '.join(text.split())}`")
                elif isinstance(c, UniqueConstraint) and len(c.columns) > 1:
                    constraints.append(f"- `{c.name}`: unique ({', '.join(col.name for col in c.columns)})")
            for index in sorted(table.indexes, key=lambda i: str(i.name)):
                if index.unique:
                    where = index.dialect_options["postgresql"].get("where")
                    suffix = f" WHERE `{where}`" if where is not None else ""
                    constraints.append(f"- `{index.name}`: unique index{suffix}")
            enums = [c for c in table.columns if type(c.type).__name__ == "Enum"]
            if enums:
                constraints.append(
                    "- Allowed values: "
                    + "; ".join(f"`{c.name}` in ({', '.join(c.type.enums)})" for c in enums)  # type: ignore[attr-defined]
                )
            if constraints:
                lines += ["", "Constraints:", "", *constraints]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    content = render()
    if "--check" in sys.argv:
        if not OUTPUT.exists() or OUTPUT.read_text() != content:
            print("docs/database/data-dictionary.md is stale: run `make data-dictionary`")
            return 1
        print("data dictionary is up to date")
        return 0
    OUTPUT.write_text(content)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
