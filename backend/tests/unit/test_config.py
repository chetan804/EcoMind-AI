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


# --- e-mail settings ---------------------------------------------------------------------------


def _mail_settings(**values: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "postgresql+psycopg://u:p@localhost/db",
        "secret_key": "unit-test-secret-key-0123456789abcdef",
    }
    base.update(values)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_email_backend_defaults_follow_the_environment() -> None:
    assert _mail_settings(environment="test").effective_email_backend == "memory"
    assert _mail_settings(environment="local").effective_email_backend == "console"
    production = _mail_settings(environment="production", refresh_cookie_secure=True)
    assert production.effective_email_backend == "none"
    assert production.email_enabled is False


@pytest.mark.parametrize("backend", ["console", "memory"])
def test_development_mail_backends_are_refused_in_production(backend: str) -> None:
    with pytest.raises(ValueError, match=r"not allowed in production|only for tests"):
        _mail_settings(environment="production", refresh_cookie_secure=True, email_backend=backend)


def test_memory_backend_is_for_tests_only() -> None:
    with pytest.raises(ValueError, match="only for tests"):
        _mail_settings(environment="local", email_backend="memory")


def test_smtp_needs_a_host_and_a_sender() -> None:
    with pytest.raises(ValueError, match="SMTP_HOST and EMAIL_FROM"):
        _mail_settings(environment="test", email_backend="smtp")


def test_smtp_in_production_needs_tls_https_links_and_paired_credentials() -> None:
    good: dict[str, object] = {
        "environment": "production",
        "refresh_cookie_secure": True,
        "email_backend": "smtp",
        "smtp_host": "mail.example.org",
        "email_from": "EcoMind <no-reply@example.org>",
        "app_base_url": "https://app.example.org/",
    }
    assert _mail_settings(**good).app_base_url == "https://app.example.org"
    with pytest.raises(ValueError, match="SMTP_SECURITY=none"):
        _mail_settings(**{**good, "smtp_security": "none"})
    with pytest.raises(ValueError, match="https in production"):
        _mail_settings(**{**good, "app_base_url": "http://app.example.org"})
    with pytest.raises(ValueError, match="set together"):
        _mail_settings(**{**good, "smtp_username": "mailer"})


def test_verification_cannot_be_required_without_delivery() -> None:
    with pytest.raises(ValueError, match="EMAIL_VERIFICATION_REQUIRED"):
        _mail_settings(environment="test", email_backend="none", email_verification_required=True)
    assert _mail_settings(environment="test", email_verification_required=True)


def test_mail_settings_reject_malformed_values() -> None:
    with pytest.raises(ValueError, match="EMAIL_FROM"):
        _mail_settings(email_backend="none", email_from="no at sign")
    with pytest.raises(ValueError, match="EMAIL_FROM"):
        _mail_settings(email_backend="none", email_from="a@example.org\r\nBcc: x@example.org")
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        _mail_settings(app_base_url="javascript:alert(1)")
    with pytest.raises(ValueError, match="APP_BASE_URL"):
        _mail_settings(app_base_url="https://user:pw@app.example.org")
    # Blank environment values mean "unset", not "invalid".
    assert _mail_settings(email_backend="", email_from=" ", smtp_host="").email_from is None


def test_mfa_is_required_for_privileged_roles_only_in_production() -> None:
    assert build().effective_mfa_required_roles == frozenset()
    production = build(
        environment="production",
        refresh_cookie_secure=True,
        cors_allowed_origins="https://app.example.org",
    )
    assert production.effective_mfa_required_roles == {"administrator", "manager"}


def test_mfa_required_roles_can_be_set_or_switched_off_explicitly() -> None:
    assert build(mfa_required_roles="administrator, collector").effective_mfa_required_roles == {
        "administrator",
        "collector",
    }
    off = build(
        environment="production",
        refresh_cookie_secure=True,
        cors_allowed_origins="https://app.example.org",
        mfa_required_roles="none",
    )
    assert off.effective_mfa_required_roles == frozenset()
    # a blank variable (an empty line in a deployment file) must not switch the policy off
    blank = build(
        environment="production",
        refresh_cookie_secure=True,
        cors_allowed_origins="https://app.example.org",
        mfa_required_roles=" ",
    )
    assert blank.effective_mfa_required_roles == {"administrator", "manager"}


def test_mfa_required_roles_must_be_real_roles() -> None:
    with pytest.raises(ValueError, match="unknown roles: admin"):
        build(mfa_required_roles="admin,manager")
