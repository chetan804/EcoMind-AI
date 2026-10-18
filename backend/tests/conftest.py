"""Shared pytest configuration.

Settings are always constructed explicitly in tests (never from a developer's .env file).
Integration tests need TEST_DATABASE_URL; see tests/fixtures/database.py.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from app.core.config import Settings

pytest_plugins = ["tests.fixtures.database"]

TEST_SECRET_KEY = "test-only-secret-key-0123456789abcdef"

SettingsFactory = Callable[..., Settings]


@pytest.fixture
def make_settings() -> SettingsFactory:
    def _make(**overrides: Any) -> Settings:
        values: dict[str, Any] = {
            "environment": "test",
            "database_url": "postgresql+psycopg://test:test@127.0.0.1:1/unused",
            "secret_key": TEST_SECRET_KEY,
        }
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return _make
