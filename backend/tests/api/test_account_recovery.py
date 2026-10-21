"""Password reset and e-mail verification: one-time links, limits, enumeration safety, audit."""

from __future__ import annotations

import datetime as dt
import re
from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.integrations.email.base import EmailDeliveryError, EmailMessage
from app.integrations.email.console import MemoryEmailSender
from app.modules.auth import policy, recovery
from app.modules.auth.models import MfaFactor
from tests.fixtures.api import (
    CSRF,
    STRONG_PASSWORD,
    ClientFactory,
    bearer,
    create_user,
    login,
)

AUTH = "/api/v1/auth"
EMAIL = "recover.me@example.org"
NEW_PASSWORD = "a brand new passphrase 77"
TOKEN = re.compile(r"#token=([A-Za-z0-9_-]+)")


def outbox(client: TestClient) -> list[EmailMessage]:
    sender = cast(MemoryEmailSender, client.app.state.email_sender)  # type: ignore[attr-defined]
    return sender.outbox


def sender_of(client: TestClient) -> MemoryEmailSender:
    return cast(MemoryEmailSender, client.app.state.email_sender)  # type: ignore[attr-defined]


def token_in(message: EmailMessage) -> str:
    match = TOKEN.search(message.body)
    assert match is not None, message.body
    return match.group(1)


def ask_reset(client: TestClient, email: str = EMAIL) -> int:
    return client.post(f"{AUTH}/password-reset/request", json={"email": email}).status_code


def confirm_reset(client: TestClient, token: str, password: str = NEW_PASSWORD) -> int:
    response = client.post(
        f"{AUTH}/password-reset/confirm", json={"token": token, "new_password": password}
    )
    return response.status_code


def reset_token(client: TestClient) -> str:
    assert ask_reset(client) == 202
    return token_in(outbox(client)[-1])


# --- configuration endpoint ------------------------------------------------------------------


def test_auth_config_reports_what_the_server_can_do(make_client: ClientFactory) -> None:
    body = make_client().get(f"{AUTH}/config").json()
    assert body == {
        "password_reset_available": True,
        "email_verification_available": True,
        "email_verification_required": False,
    }
    disabled = make_client(email_backend="none").get(f"{AUTH}/config").json()
    assert disabled["password_reset_available"] is False
    assert disabled["email_verification_available"] is False


def test_requests_fail_honestly_when_email_is_not_configured(
    make_client: ClientFactory, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    client = make_client(email_backend="none")
    for path in ("password-reset/request", "email-verification/request"):
        response = client.post(f"{AUTH}/{path}", json={"email": EMAIL})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "email_not_configured"


# --- password reset --------------------------------------------------------------------------


def test_reset_request_sends_one_link_to_the_account_address(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL, full_name="Rita Recover")
    response = client.post(f"{AUTH}/password-reset/request", json={"email": EMAIL.upper()})
    assert response.status_code == 202
    assert response.headers["cache-control"] == "no-store"
    [message] = outbox(client)
    assert message.to == EMAIL
    assert message.purpose == "password_reset"
    assert "Rita Recover" in message.body
    assert "/reset-password#token=" in message.body  # fragment, so it stays out of server logs
    assert "?token=" not in message.body
    assert token_in(message) not in response.text


def test_reset_request_answers_identically_for_unknown_and_inactive_addresses(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    create_user(db_engine, email="gone@example.org", active=False)
    known = client.post(f"{AUTH}/password-reset/request", json={"email": EMAIL})
    outbox(client).clear()
    unknown = client.post(f"{AUTH}/password-reset/request", json={"email": "nobody@example.org"})
    inactive = client.post(f"{AUTH}/password-reset/request", json={"email": "gone@example.org"})
    garbage = client.post(f"{AUTH}/password-reset/request", json={"email": "not an address"})
    for other in (unknown, inactive, garbage):
        assert other.status_code == known.status_code == 202
        assert other.json() == known.json()
        assert set(other.headers) >= {"cache-control"}
    assert outbox(client) == []


def test_reset_replaces_the_password_ends_sessions_and_notifies(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    login(client, EMAIL)  # leaves a refresh cookie in this client's jar
    token = reset_token(client)

    assert confirm_reset(client, token) == 204
    # The refresh session from before the reset is dead.
    assert client.post(f"{AUTH}/refresh", headers=CSRF).status_code == 401
    old = client.post(f"{AUTH}/login", json={"email": EMAIL, "password": STRONG_PASSWORD})
    assert old.status_code == 401
    assert (
        client.post(f"{AUTH}/login", json={"email": EMAIL, "password": NEW_PASSWORD}).status_code
        == 200
    )
    notice = outbox(client)[-1]
    assert notice.purpose == "password_changed_notice"
    assert "#token=" not in notice.body  # a notice carries no link


def test_a_reset_link_works_once(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=EMAIL)
    token = reset_token(client)
    assert confirm_reset(client, token) == 204
    again = client.post(
        f"{AUTH}/password-reset/confirm",
        json={"token": token, "new_password": "yet another passphrase 88"},
    )
    assert again.status_code == 400
    assert again.json()["error"]["code"] == "invalid_or_expired_token"
    assert (
        client.post(f"{AUTH}/login", json={"email": EMAIL, "password": NEW_PASSWORD}).status_code
        == 200
    )


def test_a_newer_link_replaces_the_older_one(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=EMAIL)
    first = reset_token(client)
    second = reset_token(client)
    assert first != second
    assert confirm_reset(client, first) == 400
    assert confirm_reset(client, second) == 204


def test_an_expired_link_is_refused(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email=EMAIL)
    token = reset_token(client)
    db_session.execute(
        text(
            "UPDATE account_tokens SET created_at = now() - interval '2 hours', "
            "expires_at = now() - interval '1 hour'"
        )
    )
    db_session.commit()
    response = client.post(
        f"{AUTH}/password-reset/confirm", json={"token": token, "new_password": NEW_PASSWORD}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_or_expired_token"


def test_unknown_tokens_get_the_same_error_as_expired_ones(client: TestClient) -> None:
    response = client.post(
        f"{AUTH}/password-reset/confirm",
        json={"token": "x" * 43, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_or_expired_token"


def test_a_weak_new_password_is_rejected_and_the_link_stays_usable(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    token = reset_token(client)
    weak = client.post(
        f"{AUTH}/password-reset/confirm", json={"token": token, "new_password": "short"}
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "weak_password"
    assert confirm_reset(client, token) == 204


def test_a_verification_link_cannot_reset_a_password(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=EMAIL)
    assert (
        client.post(f"{AUTH}/email-verification/request", json={"email": EMAIL}).status_code == 202
    )
    verification = token_in(outbox(client)[-1])
    assert confirm_reset(client, verification) == 400


def test_reset_keeps_two_factor_authentication(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    user_id = create_user(db_engine, email=EMAIL)
    db_session.add(
        MfaFactor(
            user_id=user_id,
            secret_encrypted="not-used-by-this-test",
            confirmed_at=dt.datetime.now(dt.UTC),
        )
    )
    db_session.commit()
    assert confirm_reset(client, reset_token(client)) == 204
    second_step = client.post(f"{AUTH}/login", json={"email": EMAIL, "password": NEW_PASSWORD})
    assert second_step.status_code == 200
    assert second_step.json()["mfa_required"] is True  # the reset did not switch MFA off


def test_a_completed_reset_clears_the_sign_in_lockout(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    for _ in range(policy.MAX_FAILED_LOGINS_PER_EMAIL):
        client.post(f"{AUTH}/login", json={"email": EMAIL, "password": "definitely wrong 1"})
    locked = client.post(f"{AUTH}/login", json={"email": EMAIL, "password": STRONG_PASSWORD})
    assert locked.status_code == 429
    assert confirm_reset(client, reset_token(client)) == 204
    assert (
        client.post(f"{AUTH}/login", json={"email": EMAIL, "password": NEW_PASSWORD}).status_code
        == 200
    )


def test_reset_proves_mailbox_control_so_it_verifies_the_address(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    assert confirm_reset(client, reset_token(client)) == 204
    token = login(client, EMAIL, NEW_PASSWORD)["access_token"]
    assert client.get(f"{AUTH}/me", headers=bearer(token)).json()["email_verified"] is True


# --- limits ----------------------------------------------------------------------------------


def test_each_address_gets_a_limited_number_of_messages_but_the_same_answer(
    client: TestClient, db_engine: Engine
) -> None:
    create_user(db_engine, email=EMAIL)
    for _ in range(policy.MAX_ACCOUNT_EMAILS_PER_ADDRESS + 2):
        assert ask_reset(client) == 202  # never reveals the throttle
    assert len(outbox(client)) == policy.MAX_ACCOUNT_EMAILS_PER_ADDRESS


def test_requests_per_ip_are_limited(client: TestClient) -> None:
    for number in range(policy.MAX_ACCOUNT_EMAIL_REQUESTS_PER_IP):
        assert ask_reset(client, f"user{number}@example.org") == 202
    blocked = client.post(f"{AUTH}/password-reset/request", json={"email": "one.more@example.org"})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1


def test_guessing_links_is_limited_per_ip(client: TestClient) -> None:
    for number in range(policy.MAX_TOKEN_REJECTIONS_PER_IP):
        assert confirm_reset(client, f"{number:02d}" + "g" * 41) == 400
    assert confirm_reset(client, "h" * 43) == 429


# --- e-mail verification ---------------------------------------------------------------------


def register(client: TestClient, email: str = "new.person@example.org") -> str:
    response = client.post(
        f"{AUTH}/register",
        json={"email": email, "password": STRONG_PASSWORD, "full_name": "New Person"},
    )
    assert response.status_code == 201, response.text
    assert response.json()["user"]["email_verified"] is False
    return str(response.json()["access_token"])


def test_registration_sends_a_verification_link_and_confirming_it_verifies(
    client: TestClient,
) -> None:
    access = register(client)
    [message] = outbox(client)
    assert message.purpose == "email_verification"
    assert client.get(f"{AUTH}/me", headers=bearer(access)).json()["email_verified"] is False

    confirm = client.post(f"{AUTH}/email-verification/confirm", json={"token": token_in(message)})
    assert confirm.status_code == 204
    assert client.get(f"{AUTH}/me", headers=bearer(access)).json()["email_verified"] is True
    reused = client.post(f"{AUTH}/email-verification/confirm", json={"token": token_in(message)})
    assert reused.status_code == 400
    assert reused.json()["error"]["code"] == "invalid_or_expired_token"


def test_registration_does_not_fail_when_the_mail_server_is_down(client: TestClient) -> None:
    sender_of(client).fail_with = EmailDeliveryError("smtp down")
    register(client)  # the account exists; the user can ask for a new link later
    assert outbox(client) == []


def test_verification_can_be_requested_again_but_not_once_verified(client: TestClient) -> None:
    register(client)
    outbox(client).clear()
    assert (
        client.post(
            f"{AUTH}/email-verification/request", json={"email": "new.person@example.org"}
        ).status_code
        == 202
    )
    [message] = outbox(client)
    client.post(f"{AUTH}/email-verification/confirm", json={"token": token_in(message)})
    outbox(client).clear()
    assert (
        client.post(
            f"{AUTH}/email-verification/request", json={"email": "new.person@example.org"}
        ).status_code
        == 202
    )
    assert outbox(client) == []  # same answer, nothing to send


def test_a_link_for_an_address_the_account_no_longer_has_is_refused(
    client: TestClient, db_session: Session
) -> None:
    register(client)
    token = token_in(outbox(client)[-1])
    db_session.execute(text("UPDATE users SET email = 'moved@example.org'"))
    db_session.commit()
    response = client.post(f"{AUTH}/email-verification/confirm", json={"token": token})
    assert response.status_code == 400
    verified = db_session.execute(text("SELECT email_verified_at FROM users")).scalar_one()
    assert verified is None


def test_sign_in_can_require_a_verified_address(
    make_client: ClientFactory, db_engine: Engine, db_session: Session
) -> None:
    client = make_client(email_verification_required=True)
    create_user(db_engine, email=EMAIL)
    refused = client.post(f"{AUTH}/login", json={"email": EMAIL, "password": STRONG_PASSWORD})
    assert refused.status_code == 403
    assert refused.json()["error"]["code"] == "email_not_verified"
    # A wrong password still gets the generic error: nothing is revealed without the password.
    wrong = client.post(f"{AUTH}/login", json={"email": EMAIL, "password": "definitely wrong 1"})
    assert wrong.status_code == 401

    # The locked-out user can still ask for a link and confirm it.
    assert (
        client.post(f"{AUTH}/email-verification/request", json={"email": EMAIL}).status_code == 202
    )
    token = token_in(outbox(client)[-1])
    assert (
        client.post(f"{AUTH}/email-verification/confirm", json={"token": token}).status_code == 204
    )
    assert login(client, EMAIL)["user"]["email_verified"] is True


# --- storage, audit and housekeeping ---------------------------------------------------------


def test_only_a_digest_of_the_token_is_stored_and_the_audit_log_holds_no_secrets(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email=EMAIL)
    token = reset_token(client)
    assert confirm_reset(client, token) == 204
    stored = db_session.execute(text("SELECT token_hash FROM account_tokens")).scalar_one()
    assert stored != token and len(stored) == 64
    dump = " ".join(
        str(row)
        for row in db_session.execute(
            text("SELECT action, changes::text, ip_address FROM audit_logs")
        )
    )
    assert token not in dump
    assert EMAIL not in dump  # addresses are recorded only as SHA-256 digests
    actions = {
        row[0]
        for row in db_session.execute(
            text("SELECT action FROM audit_logs WHERE action LIKE 'auth.password_reset%'")
        )
    }
    assert actions == {"auth.password_reset_requested", "auth.password_reset_completed"}


def test_rejections_are_audited_with_a_reason(client: TestClient, db_session: Session) -> None:
    confirm_reset(client, "z" * 43)
    reason = db_session.execute(
        text(
            "SELECT changes->>'reason' FROM audit_logs WHERE action = 'auth.account_token_rejected'"
        )
    ).scalar_one()
    assert reason == "unknown"


def test_a_failed_delivery_never_breaks_the_request_or_logs_the_link(
    client: TestClient, db_engine: Engine, caplog: pytest.LogCaptureFixture
) -> None:
    create_user(db_engine, email=EMAIL)
    sender_of(client).fail_with = EmailDeliveryError("SMTP delivery failed: OSError")
    with caplog.at_level("ERROR"):
        assert ask_reset(client) == 202
    assert any("email.delivery_failed" in r.getMessage() for r in caplog.records)
    for record in caplog.records:
        assert EMAIL not in record.getMessage()
        assert "#token=" not in record.getMessage()


def test_changing_the_password_sends_a_notice(client: TestClient, db_engine: Engine) -> None:
    create_user(db_engine, email=EMAIL)
    access = login(client, EMAIL)["access_token"]
    changed = client.post(
        f"{AUTH}/change-password",
        headers=bearer(access),
        json={"current_password": STRONG_PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 200
    assert [m.purpose for m in outbox(client)] == ["password_changed_notice"]


def test_purge_removes_only_old_expired_or_used_tokens(
    client: TestClient, db_engine: Engine, db_session: Session
) -> None:
    create_user(db_engine, email=EMAIL)
    reset_token(client)  # a live token
    reset_token(client)  # replaces the first one: consumed, but only just now
    db_session.execute(
        text(
            "INSERT INTO account_tokens (user_id, purpose, token_hash, email, created_at, expires_at) "
            "SELECT id, 'password_reset', repeat('a', 64), email, "
            "now() - interval '10 days', now() - interval '9 days' FROM users"
        )
    )
    db_session.commit()
    removed = recovery.purge_expired_tokens(db_session, keep_days=7)
    assert removed == 1
    assert db_session.execute(text("SELECT count(*) FROM account_tokens")).scalar_one() == 2
