from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app import cli
from app.db import session as db_session_module
from tests.conftest import SettingsFactory
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


# -- model registry commands --------------------------------------------------------------------
@pytest.fixture
def model_cli(
    cli_env: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
) -> Engine:
    from pathlib import Path

    from app.core.config import Settings

    artifacts = Path(str(tmp_path)) / "artifacts"
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="postgresql+psycopg://test:test@127.0.0.1:1/unused",
        secret_key="x" * 40,
        model_artifacts_dir=artifacts,
    )
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    return cli_env


def test_register_then_activate_a_model_from_the_command_line(
    model_cli: Engine, tmp_path: pytest.TempPathFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    from pathlib import Path

    from tests.fixtures.classification import write_artifact

    write_artifact(Path(str(tmp_path)) / "artifacts", "1.0.0")
    assert cli.main(["register-model", "--version", "1.0.0"]) == 0
    assert "registered (candidate)" in capsys.readouterr().out
    assert cli.main(["register-model", "--version", "1.0.0"]) == 0  # idempotent
    assert cli.main(["activate-model", "--version", "1.0.0"]) == 0
    assert "is now active" in capsys.readouterr().out
    with model_cli.connect() as connection:
        assert (
            connection.execute(
                text("SELECT status FROM classification_model_versions")
            ).scalar_one()
            == "active"
        )
        assert (
            connection.execute(
                text(
                    "SELECT count(*) FROM audit_logs WHERE action = 'classification.model_activated'"
                )
            ).scalar_one()
            == 1
        )


def test_model_commands_fail_clearly_when_there_is_nothing_to_use(
    model_cli: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["register-model", "--version", "9.9.9"]) == 1
    assert "No artifact" in capsys.readouterr().err
    assert cli.main(["activate-model", "--version", "9.9.9"]) == 1
    assert "Expected exactly one registered model" in capsys.readouterr().err


def test_support_commands_seed_help_and_purge_old_conversations(
    cli_env: Engine,
    make_settings: SettingsFactory,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Settings are built explicitly: the test must not depend on the shell's environment.
    monkeypatch.setattr(cli, "get_settings", lambda: make_settings(assistant_retention_days=90))
    assert cli.main(["seed-support-knowledge"]) == 0
    assert "31 created, 0 updated" in capsys.readouterr().out
    assert cli.main(["seed-support-knowledge"]) == 0  # idempotent
    assert "0 created, 0 updated" in capsys.readouterr().out

    from tests.fixtures.api import create_user

    user = create_user(cli_env, email="chatter@example.org")
    with cli_env.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO assistant_conversations (user_id, updated_at) "
                "VALUES (:u, now() - interval '400 days'), (:u, now())"
            ),
            {"u": user},
        )
    assert cli.main(["purge-assistant-conversations"]) == 0
    assert "removed 1 assistant conversation" in capsys.readouterr().out
    with cli_env.connect() as connection:
        left = connection.execute(text("SELECT count(*) FROM assistant_conversations")).scalar_one()
    assert left == 1


def test_reference_import_without_the_public_data_clone_explains_itself(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(*, key: str) -> str:
        raise RuntimeError(f"msw-src is not available for {key}")

    monkeypatch.setattr(cli, "import_reference", missing)
    assert cli.main(["import-reference-series", "--key", "austin"]) == 1
    error = capsys.readouterr().err
    assert "git clone" in error and "msw-src" in error and "Traceback" not in error
