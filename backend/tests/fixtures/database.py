"""Isolated PostgreSQL databases for integration tests.

``TEST_DATABASE_URL`` points at a PostgreSQL *server* whose role may CREATE DATABASE (for
example ``postgresql+psycopg://postgres:postgres@localhost:5432/postgres``). Every test that needs
a database gets a brand-new, uniquely named database (``ecomind_test_<random>``) that is dropped
afterwards. The database named in TEST_DATABASE_URL itself is only used to issue
CREATE/DROP DATABASE and is never modified, so application or development data cannot be touched.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url

BACKEND_ROOT = Path(__file__).resolve().parents[2]
DB_PREFIX = "ecomind_test_"


def _admin_url() -> URL | None:
    raw = os.environ.get("TEST_DATABASE_URL")
    return make_url(raw) if raw else None


def alembic_config() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def upgrade(engine: Engine, revision: str = "head") -> None:
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


def downgrade(engine: Engine, revision: str = "base") -> None:
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, revision)


@pytest.fixture
def empty_database_url() -> Iterator[URL]:
    """URL of a new, empty, isolated database (dropped after the test)."""
    admin = _admin_url()
    if admin is None:
        if os.environ.get("CI"):
            # On CI a missing database must fail loudly instead of silently skipping coverage.
            pytest.fail("TEST_DATABASE_URL must be set when CI is set")
        pytest.skip("TEST_DATABASE_URL is not set; integration tests need a PostgreSQL server")
    name = f"{DB_PREFIX}{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(admin, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    try:
        yield admin.set(database=name)
    finally:
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin_engine.dispose()


@pytest.fixture
def empty_engine(empty_database_url: URL) -> Iterator[Engine]:
    engine = create_engine(empty_database_url)
    yield engine
    engine.dispose()


@pytest.fixture
def migrated_engine(empty_engine: Engine) -> Engine:
    """Engine bound to an isolated database upgraded to the Alembic head."""
    upgrade(empty_engine)
    return empty_engine
