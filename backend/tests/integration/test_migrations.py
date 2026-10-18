"""Migration tests: run against a brand-new isolated PostgreSQL database (never a shared one)."""

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect

from app.db.metadata import target_metadata
from tests.fixtures.database import downgrade, upgrade

pytestmark = pytest.mark.integration


def table_names(engine: Engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_creates_every_registered_table(migrated_engine: Engine) -> None:
    assert table_names(migrated_engine) == set(target_metadata.tables)


def test_models_and_migrations_have_no_drift(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, target_metadata) == []


def test_downgrade_removes_everything_and_upgrade_is_repeatable(migrated_engine: Engine) -> None:
    downgrade(migrated_engine)
    assert table_names(migrated_engine) == set()
    upgrade(migrated_engine)
    assert table_names(migrated_engine) == set(target_metadata.tables)


def test_every_foreign_key_column_is_indexed_or_part_of_a_key(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    unindexed: list[str] = []
    for table in inspector.get_table_names():
        covered = {tuple(ix["column_names"][:1]) for ix in inspector.get_indexes(table)}
        covered |= {
            (c,) for uc in inspector.get_unique_constraints(table) for c in uc["column_names"][:1]
        }
        covered.add(tuple(inspector.get_pk_constraint(table)["constrained_columns"][:1]))
        for fk in inspector.get_foreign_keys(table):
            if tuple(fk["constrained_columns"][:1]) not in covered:
                unindexed.append(f"{table}.{fk['constrained_columns']}")
    assert unindexed == []


def test_every_enum_column_has_a_check_constraint(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    missing: list[str] = []
    for table in target_metadata.tables.values():
        checks = " ".join(c["sqltext"] for c in inspector.get_check_constraints(table.name))
        for column in table.columns:
            if type(column.type).__name__ == "Enum" and f"{column.name}" not in checks:
                missing.append(f"{table.name}.{column.name}")
    assert missing == []


def test_every_table_has_a_uuid_primary_key_except_join_tables(migrated_engine: Engine) -> None:
    inspector = inspect(migrated_engine)
    join_tables = {"user_roles", "role_permissions"}
    for table in inspector.get_table_names():
        if table in join_tables or table == "alembic_version":
            continue
        assert inspector.get_pk_constraint(table)["constrained_columns"] == ["id"], table
