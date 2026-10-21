"""SMTP delivery with the standard library (STARTTLS or implicit TLS, certificate verified)."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage as MimeMessage
from email.policy import SMTP as SMTP_POLICY
from email.utils import formatdate, make_msgid, parseaddr
from typing import Literal

from app.integrations.email.base import EmailDeliveryError, EmailMessage


class SmtpEmailSender:
    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        sender: str,
        username: str | None = None,
        password: str | None = None,
        security: Literal["starttls", "ssl", "none"] = "starttls",
        timeout_seconds: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._sender = sender
        self._username = username
        self._password = password
        self._security = security
        self._timeout = timeout_seconds

    def build(self, message: EmailMessage) -> MimeMessage:
        mime = MimeMessage(policy=SMTP_POLICY)
        mime["From"] = self._sender  # the SMTP policy rejects CR/LF in headers (header injection)
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime["Date"] = formatdate(localtime=False)
        mime["Message-ID"] = make_msgid(domain=parseaddr(self._sender)[1].rpartition("@")[2])
        mime["Auto-Submitted"] = "auto-generated"
        mime.set_content(message.body)
        return mime

    def send(self, message: EmailMessage) -> None:
        try:
            mime = self.build(message)
            context = ssl.create_default_context()
            if self._security == "ssl":
                with smtplib.SMTP_SSL(
                    self._host, self._port, timeout=self._timeout, context=context
                ) as smtp:
                    self._deliver(smtp, mime)
            else:
                with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                    if self._security == "starttls":
                        smtp.starttls(context=context)
                    self._deliver(smtp, mime)
        except (smtplib.SMTPException, OSError, ValueError) as exc:
            # Never include the message body (it holds a one-time link) in the error.
            raise EmailDeliveryError(f"SMTP delivery failed: {type(exc).__name__}") from exc

    def _deliver(self, smtp: smtplib.SMTP, mime: MimeMessage) -> None:
        if self._username is not None and self._password is not None:
            smtp.login(self._username, self._password)
        smtp.send_message(mime)
