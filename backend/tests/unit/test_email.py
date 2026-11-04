"""E-mail adapters: SMTP against a local protocol-level server, factory and safe delivery."""

from __future__ import annotations

import logging
import socket
import socketserver
import threading
from collections.abc import Iterator
from email import message_from_bytes
from email.message import Message

import pytest

from app.core.config import Settings
from app.integrations.email.base import EmailDeliveryError, EmailMessage
from app.integrations.email.console import ConsoleEmailSender, MemoryEmailSender
from app.integrations.email.factory import (
    DisabledEmailSender,
    build_email_sender,
    deliver,
)
from app.integrations.email.smtp import SmtpEmailSender

MESSAGE = EmailMessage(
    to="rita@example.org",
    subject="Reset your password",
    body="Open https://app.example.org/reset-password#token=abc\n",
    purpose="password_reset",
)


class _Handler(socketserver.StreamRequestHandler):
    """The smallest SMTP server that completes one delivery (no TLS, no AUTH)."""

    def handle(self) -> None:
        server: _Server = self.server  # type: ignore[assignment]
        self._say("220 test ESMTP")
        data_mode = False
        lines: list[bytes] = []
        for raw in self.rfile:
            line = raw.rstrip(b"\r\n")
            if data_mode:
                if line == b".":
                    data_mode = False
                    server.messages.append(message_from_bytes(b"\r\n".join(lines)))
                    self._say("250 queued")
                else:
                    lines.append(line[1:] if line.startswith(b"..") else line)
                continue
            command = line.decode().upper()
            if command.startswith("EHLO"):
                self._say("250 test")
            elif command.startswith(("MAIL", "RCPT")):
                server.envelope.append(line.decode())
                self._say("250 ok")
            elif command == "DATA":
                data_mode = True
                self._say("354 go")
            elif command == "QUIT":
                self._say("221 bye")
                return
            else:
                self._say("502 not implemented")

    def _say(self, text: str) -> None:
        self.wfile.write(text.encode() + b"\r\n")


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.messages: list[Message] = []
        self.envelope: list[str] = []


@pytest.fixture
def smtp_server() -> Iterator[_Server]:
    server = _Server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _sender(port: int, **overrides: object) -> SmtpEmailSender:
    values: dict[str, object] = {
        "host": "127.0.0.1",
        "port": port,
        "sender": "EcoMind AI <no-reply@example.org>",
        "security": "none",
        "timeout_seconds": 3.0,
    }
    values.update(overrides)
    return SmtpEmailSender(**values)  # type: ignore[arg-type]


def test_smtp_delivers_a_plain_text_message(smtp_server: _Server) -> None:
    _sender(smtp_server.server_address[1]).send(MESSAGE)
    [received] = smtp_server.messages
    assert received["To"] == "rita@example.org"
    assert received["From"] == "EcoMind AI <no-reply@example.org>"
    assert received["Subject"] == "Reset your password"
    assert received["Auto-Submitted"] == "auto-generated"
    assert received["Message-ID"].endswith("@example.org>")
    assert received.get_content_type() == "text/plain"
    payload = received.get_payload(decode=True)
    assert isinstance(payload, bytes)
    assert b"#token=abc" in payload
    assert any("rita@example.org" in line for line in smtp_server.envelope)


def test_smtp_rejects_header_injection(smtp_server: _Server) -> None:
    evil = EmailMessage(
        to="rita@example.org",
        subject="Hi\r\nBcc: attacker@example.org",
        body="x",
        purpose="test",
    )
    with pytest.raises(EmailDeliveryError):
        _sender(smtp_server.server_address[1]).send(evil)
    assert smtp_server.messages == []


def test_smtp_connection_failure_becomes_a_delivery_error_without_the_body() -> None:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]
    with pytest.raises(EmailDeliveryError) as raised:
        _sender(closed_port).send(MESSAGE)
    assert "#token" not in str(raised.value)
    assert isinstance(raised.value.__cause__, OSError)


def test_starttls_is_required_when_the_server_does_not_offer_it(smtp_server: _Server) -> None:
    with pytest.raises(EmailDeliveryError):
        _sender(smtp_server.server_address[1], security="starttls").send(MESSAGE)
    assert smtp_server.messages == []  # nothing is ever sent in clear text by mistake


def test_deliver_logs_failures_without_recipient_or_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sender = MemoryEmailSender()
    sender.fail_with = EmailDeliveryError("SMTP delivery failed: OSError")
    with caplog.at_level(logging.ERROR):
        assert deliver(sender, MESSAGE) is False
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "password_reset" in text
    assert "rita@example.org" not in text
    assert "#token" not in text


def test_memory_and_console_backends() -> None:
    memory = MemoryEmailSender()
    assert deliver(memory, MESSAGE) is True
    assert memory.outbox == [MESSAGE]
    ConsoleEmailSender().send(MESSAGE)  # logs only; must not raise


def test_disabled_backend_fails_loudly() -> None:
    with pytest.raises(EmailDeliveryError):
        DisabledEmailSender().send(MESSAGE)


def _settings(**values: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "postgresql+psycopg://u:p@localhost/db",
        "secret_key": "unit-test-secret-key-0123456789abcdef",
        "environment": "test",
    }
    base.update(values)
    return Settings(_env_file=None, **base)  # type: ignore[arg-type]


def test_factory_picks_the_backend_from_settings() -> None:
    assert build_email_sender(_settings()).name == "memory"
    assert build_email_sender(_settings(email_backend="none")).name == "none"
    assert build_email_sender(_settings(environment="local")).name == "console"
    smtp = build_email_sender(
        _settings(email_backend="smtp", smtp_host="mail.example.org", email_from="a@example.org")
    )
    assert smtp.name == "smtp"


class _FlakySender:
    """Fails with the given errors in order, then succeeds."""

    name = "flaky"

    def __init__(self, *errors: EmailDeliveryError) -> None:
        self.errors = list(errors)
        self.calls = 0

    def send(self, message: EmailMessage) -> None:
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)


def test_a_transient_failure_is_retried_with_backoff_and_then_delivered(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sender = _FlakySender(
        EmailDeliveryError("SMTP delivery failed: OSError", transient=True),
        EmailDeliveryError("SMTP delivery failed: SMTPServerDisconnected", transient=True),
    )
    waits: list[float] = []
    with caplog.at_level(logging.INFO):
        assert deliver(sender, MESSAGE, sleep=waits.append) is True
    assert sender.calls == 3 and waits == [0.5, 2.0]
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "email.delivered" in text and "attempts=3" in text
    assert "rita@example.org" not in text


def test_retries_are_bounded_and_the_final_failure_is_logged_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sender = _FlakySender(
        *[EmailDeliveryError("SMTP delivery failed: OSError", transient=True)] * 5
    )
    with caplog.at_level(logging.INFO):
        assert deliver(sender, MESSAGE, max_attempts=3, sleep=lambda _s: None) is False
    assert sender.calls == 3
    failures = [r for r in caplog.records if "email.delivery_failed" in r.getMessage()]
    assert len(failures) == 1 and "attempts=3" in failures[0].getMessage()


def test_a_permanent_failure_is_never_retried() -> None:
    sender = _FlakySender(EmailDeliveryError("SMTP delivery failed: SMTPRecipientsRefused"))
    assert deliver(sender, MESSAGE, sleep=lambda _s: pytest.fail("must not wait")) is False
    assert sender.calls == 1


def test_smtp_errors_are_classified_as_transient_or_permanent() -> None:
    import smtplib

    from app.integrations.email.smtp import _is_transient

    assert _is_transient(TimeoutError())
    assert _is_transient(ConnectionRefusedError())
    assert _is_transient(smtplib.SMTPServerDisconnected())
    assert _is_transient(smtplib.SMTPResponseException(451, b"try again later"))
    assert not _is_transient(smtplib.SMTPResponseException(550, b"mailbox unavailable"))
    assert not _is_transient(smtplib.SMTPAuthenticationError(535, b"bad credentials"))
    assert not _is_transient(smtplib.SMTPRecipientsRefused({}))
    assert not _is_transient(ValueError("header injection"))
