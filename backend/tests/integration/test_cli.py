from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app import cli
from app.db import session as db_session_module
from tests.fixtures.api import bearer, login


@pytest.fixture
def cli_env(db_engine: Engine, monkeypatch: pytest.MonkeyPatch) -> Engine:
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(cli, "get_session_factory", lambda: factory)
    monkeypatch.setattr(db_session_module, "get_session_factory", lambda: factory)
    return db_engine


def test_create_admin_creates_a_working_administrator(
    cli_env: Engine, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ECOMIND_ADMIN_PASSWORD", "a long admin passphrase 2026")
    assert cli.main(["create-admin", "--email", "Root@Example.org", "--name", "Site Admin"]) == 0
    body = login(client, "root@example.org", "a long admin passphrase 2026")
    assert body["user"]["roles"] == ["administrator"]
    assert "users:manage" in body["user"]["permissions"]
    assert client.get("/api/v1/auth/me", headers=bearer(body["access_token"])).status_code == 200
    with cli_env.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM audit_logs WHERE action = 'users.admin_created_by_cli'")
            ).scalar_one()
            == 1
        )


def test_create_admin_enforces_policy_and_uniqueness(
    cli_env: Engine, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ECOMIND_ADMIN_PASSWORD", "short")
    assert cli.main(["create-admin", "--email", "a@example.org", "--name", "Admin User"]) == 1
    assert "password policy" in capsys.readouterr().err

    monkeypatch.setenv("ECOMIND_ADMIN_PASSWORD", "a long admin passphrase 2026")
    assert cli.main(["create-admin", "--email", "a@example.org", "--name", "Admin User"]) == 0
    assert cli.main(["create-admin", "--email", "A@example.org", "--name", "Admin User"]) == 1
    assert "already exists" in capsys.readouterr().err
