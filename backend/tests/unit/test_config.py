from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from tests.conftest import TEST_SECRET_KEY


def build(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": "local",
        "database_url": "postgresql+psycopg://u:p@localhost/db",
        "secret_key": "a-sufficiently-long-random-secret-value-1234",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_missing_required_values_fail_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None)
    missing = {error["loc"][0] for error in excinfo.value.errors()}
    assert {"database_url", "secret_key"} <= missing


def test_cors_origins_parsed_from_comma_separated_string() -> None:
    settings = build(cors_allowed_origins="http://a.test, http://b.test ,")
    assert settings.cors_allowed_origins == ["http://a.test", "http://b.test"]


def test_database_must_be_postgresql() -> None:
    with pytest.raises(ValidationError, match="PostgreSQL"):
        build(database_url="sqlite:///x.db")


def test_short_secret_rejected() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        build(secret_key="short")


def test_example_placeholder_secret_rejected_outside_test() -> None:
    placeholder = "CHANGE_ME_generate_a_random_value_with_at_least_32_characters"
    with pytest.raises(ValidationError, match="placeholder"):
        build(secret_key=placeholder)
    assert build(environment="test", secret_key=placeholder)


def test_secret_is_not_exposed_in_repr() -> None:
    assert "sufficiently-long" not in repr(build())


def test_production_requires_secure_cookie_and_explicit_origins() -> None:
    with pytest.raises(ValidationError, match="REFRESH_COOKIE_SECURE"):
        build(environment="production", refresh_cookie_secure=False)
    with pytest.raises(ValidationError, match=r"'\*'"):
        build(environment="production", refresh_cookie_secure=True, cors_allowed_origins="*")
    assert build(
        environment="production",
        refresh_cookie_secure=True,
        cors_allowed_origins="https://app.example.org",
    ).is_production


def test_samesite_none_requires_secure_cookie() -> None:
    with pytest.raises(ValidationError, match="SAMESITE"):
        build(refresh_cookie_samesite="none", refresh_cookie_secure=False)


def test_test_secret_constant_is_valid() -> None:
    assert len(TEST_SECRET_KEY) >= 32
