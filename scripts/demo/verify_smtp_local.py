#!/usr/bin/env python3
"""Send one message through the backend's SMTP adapter to a LOCAL third-party SMTP server.

The server is `aiosmtpd` (an independent SMTP implementation) with STARTTLS and mandatory AUTH and
a throw-away self-signed certificate. This checks the adapter against a server it was not written
alongside; it does NOT prove delivery through a real provider (that needs real credentials).

  pip install aiosmtpd           # not a project dependency; install it only for this check
  PYTHONPATH=backend python3 scripts/demo/verify_smtp_local.py

Needs the `openssl` command. Exits 0 when the message arrives with the right content, and when a
wrong password and an untrusted certificate are both refused.
"""

from __future__ import annotations

import os
import secrets
import socket
import ssl
import subprocess
import sys
import tempfile
from pathlib import Path

from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

from app.integrations.email.base import EmailDeliveryError, EmailMessage
from app.integrations.email.smtp import SmtpEmailSender

USERNAME = "demo-mailer"
PASSWORD = secrets.token_urlsafe(18)
MESSAGE = EmailMessage(
    to="rita@example.org",
    subject="Reset your password",
    body="Open https://app.example.org/reset-password#token=abc\n",
    purpose="password_reset",
)


class Inbox:
    def __init__(self) -> None:
        self.received: list[object] = []

    async def handle_DATA(self, server, session, envelope):  # noqa: ANN001, N802
        self.received.append(envelope)
        return "250 queued"


def authenticator(server, session, envelope, mechanism, auth_data):  # noqa: ANN001
    if isinstance(auth_data, LoginPassword) and (
        auth_data.login.decode(),
        auth_data.password.decode(),
    ) == (USERNAME, PASSWORD):
        return AuthResult(success=True)
    return AuthResult(success=False, handled=False)


def make_certificate(directory: Path) -> Path:
    cert, key = directory / "cert.pem", directory / "key.pem"
    subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-subj", "/CN=127.0.0.1", "-addext", "subjectAltName=IP:127.0.0.1",
            "-keyout", str(key), "-out", str(cert),
        ],
        check=True,
        capture_output=True,
    )  # fmt: skip
    return cert


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        cert = make_certificate(directory)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, directory / "key.pem")
        inbox = Inbox()
        with socket.socket() as probe:  # aiosmtpd cannot bind port 0 and then connect to itself
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        controller = Controller(
            inbox,
            hostname="127.0.0.1",
            port=port,
            tls_context=context,
            require_starttls=True,
            auth_required=True,
            auth_require_tls=True,
            authenticator=authenticator,
        )
        controller.start()
        try:
            os.environ["SSL_CERT_FILE"] = str(cert)  # trust the throw-away certificate only

            def sender(password: str) -> SmtpEmailSender:
                return SmtpEmailSender(
                    host="127.0.0.1",
                    port=port,
                    sender="EcoMind AI Demo <no-reply@example.org>",
                    username=USERNAME,
                    password=password,
                    security="starttls",
                    timeout_seconds=5,
                )

            sender(PASSWORD).send(MESSAGE)
            assert len(inbox.received) == 1, "the message did not arrive"
            body = inbox.received[0].content.decode()  # type: ignore[attr-defined]
            assert "Subject: Reset your password" in body and "#token=abc" in body
            print("OK  delivered over STARTTLS with AUTH; subject and link intact")

            try:
                sender("wrong-" + PASSWORD).send(MESSAGE)
            except EmailDeliveryError as exc:
                print(f"OK  wrong password refused ({exc})")
            else:
                print("FAIL wrong password was accepted")
                return 1
            assert len(inbox.received) == 1

            os.environ["SSL_CERT_FILE"] = "/nonexistent"  # no trust anchor: verification must fail
            try:
                sender(PASSWORD).send(MESSAGE)
            except EmailDeliveryError as exc:
                print(f"OK  untrusted certificate refused ({exc})")
            else:
                print("FAIL untrusted certificate was accepted")
                return 1
            assert len(inbox.received) == 1
        finally:
            controller.stop()
    print("all local SMTP checks passed (real provider delivery is NOT verified by this script)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
