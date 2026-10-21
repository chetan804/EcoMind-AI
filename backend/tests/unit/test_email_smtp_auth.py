"""SMTP with AUTH and STARTTLS against a local protocol-level server using a throw-away certificate.

This is what a real provider (or the demo Mailpit container) requires: the client upgrades to TLS
with the certificate verified, then authenticates, and only then sends. The certificate is created
here for 127.0.0.1 and trusted for the test only (``SSL_CERT_FILE``); no real service is contacted.
"""

from __future__ import annotations

import base64
import datetime as dt
import ipaddress
import secrets
import socketserver
import ssl
import threading
from collections.abc import Iterator
from email import message_from_bytes
from email.message import Message
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from app.integrations.email.base import EmailDeliveryError, EmailMessage
from app.integrations.email.smtp import SmtpEmailSender

MESSAGE = EmailMessage(
    to="rita@example.org",
    subject="Reset your password",
    body="Open https://app.example.org/reset-password#token=abc\n",
    purpose="password_reset",
)
# Generated per run: no credential literal lives in the repository.
USERNAME = "demo-mail-user"
PASSWORD = secrets.token_urlsafe(12)


def _make_certificate(directory: Path) -> tuple[Path, Path]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = dt.datetime.now(dt.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(hours=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_path = directory / "server.pem"
    key_path = directory / "server.key"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


class _Handler(socketserver.StreamRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.tls = False
        self.authenticated = False

    def handle(self) -> None:
        server: _Server = self.server  # type: ignore[assignment]
        self._say("220 test ESMTP")
        data_mode = False
        lines: list[bytes] = []
        while raw := self.rfile.readline():
            line = raw.rstrip(b"\r\n")
            if data_mode:
                if line == b".":
                    data_mode = False
                    server.messages.append(message_from_bytes(b"\r\n".join(lines)))
                    self._say("250 queued")
                else:
                    lines.append(line[1:] if line.startswith(b"..") else line)
                continue
            text = line.decode()
            command = text.upper()
            if command.startswith("EHLO"):
                self._ehlo()
            elif command == "STARTTLS":
                self._say("220 ready")
                try:
                    self._upgrade(server)
                except (ssl.SSLError, OSError):
                    return  # the client refused our certificate and hung up
            elif command.startswith("AUTH "):
                self._auth(server, text)
            elif command.startswith(("MAIL", "RCPT")):
                if not self.authenticated:
                    self._say("530 authentication required")
                else:
                    self._say("250 ok")
            elif command == "DATA":
                data_mode = True
                self._say("354 go")
            elif command == "QUIT":
                self._say("221 bye")
                return
            else:
                self._say("502 not implemented")

    def _ehlo(self) -> None:
        extensions = ["test"]
        if not self.tls:
            extensions.append("STARTTLS")
        else:
            extensions.append("AUTH PLAIN LOGIN")
        for index, extension in enumerate(extensions):
            self._say(f"250{'-' if index < len(extensions) - 1 else ' '}{extension}")

    def _upgrade(self, server: _Server) -> None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(server.cert_path, server.key_path)
        secured = context.wrap_socket(self.connection, server_side=True)
        self.connection = secured
        self.rfile = secured.makefile("rb")
        self.wfile = secured.makefile("wb", buffering=0)  # type: ignore[assignment]
        self.tls = True

    def _auth(self, server: _Server, text: str) -> None:
        if not self.tls:
            self._say("530 must issue a STARTTLS command first")
            return
        parts = text.split()
        if parts[1].upper() == "PLAIN" and len(parts) == 3:
            _, user, password = base64.b64decode(parts[2]).decode().split("\0")
        elif parts[1].upper() == "LOGIN":
            self._say("334 " + base64.b64encode(b"Username:").decode())
            user = base64.b64decode(self.rfile.readline().strip()).decode()
            self._say("334 " + base64.b64encode(b"Password:").decode())
            password = base64.b64decode(self.rfile.readline().strip()).decode()
        else:
            self._say("504 mechanism not supported")
            return
        server.attempts.append(user)
        if (user, password) == (USERNAME, PASSWORD):
            self.authenticated = True
            self._say("235 authenticated")
        else:
            self._say("535 authentication failed")

    def _say(self, text: str) -> None:
        self.wfile.write(text.encode() + b"\r\n")


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, cert_path: Path, key_path: Path) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.cert_path = cert_path
        self.key_path = key_path
        self.messages: list[Message] = []
        self.attempts: list[str] = []


@pytest.fixture
def smtp_tls_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Server]:
    cert_path, key_path = _make_certificate(tmp_path)
    monkeypatch.setenv("SSL_CERT_FILE", str(cert_path))  # trust the test certificate only
    server = _Server(cert_path, key_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def _sender(server: _Server, **overrides: object) -> SmtpEmailSender:
    values: dict[str, object] = {
        "host": "127.0.0.1",
        "port": server.server_address[1],
        "sender": "EcoMind AI <no-reply@example.org>",
        "username": USERNAME,
        "password": PASSWORD,
        "security": "starttls",
        "timeout_seconds": 5.0,
    }
    values.update(overrides)
    return SmtpEmailSender(**values)  # type: ignore[arg-type]


def test_starttls_then_auth_then_delivery(smtp_tls_server: _Server) -> None:
    _sender(smtp_tls_server).send(MESSAGE)
    [received] = smtp_tls_server.messages
    assert received["To"] == "rita@example.org"
    assert smtp_tls_server.attempts == [USERNAME]


def test_wrong_password_is_refused_and_nothing_is_delivered(smtp_tls_server: _Server) -> None:
    with pytest.raises(EmailDeliveryError) as raised:
        _sender(smtp_tls_server, password="not-the-password").send(MESSAGE)
    assert "SMTPAuthenticationError" in str(raised.value)
    assert "not-the-password" not in str(raised.value)  # a credential never reaches the error
    assert smtp_tls_server.messages == []


def test_missing_credentials_are_refused_by_a_server_that_requires_them(
    smtp_tls_server: _Server,
) -> None:
    with pytest.raises(EmailDeliveryError):
        _sender(smtp_tls_server, username=None, password=None).send(MESSAGE)
    assert smtp_tls_server.messages == []


def test_an_untrusted_certificate_is_never_accepted(
    smtp_tls_server: _Server, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    other_cert, _ = _make_certificate(other_dir)
    monkeypatch.setenv("SSL_CERT_FILE", str(other_cert))  # trust a different authority
    with pytest.raises(EmailDeliveryError) as raised:
        _sender(smtp_tls_server).send(MESSAGE)
    assert "SSLCertVerificationError" in str(raised.value) or "SSLError" in str(raised.value)
    assert smtp_tls_server.attempts == []  # the credentials were not sent over the untrusted link
    assert smtp_tls_server.messages == []
