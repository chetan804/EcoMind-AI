"""Choose the e-mail backend from settings (``EMAIL_BACKEND``) and deliver safely."""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.integrations.email.base import EmailDeliveryError, EmailMessage, EmailSender
from app.integrations.email.console import ConsoleEmailSender, MemoryEmailSender
from app.integrations.email.smtp import SmtpEmailSender

logger = logging.getLogger(__name__)


class DisabledEmailSender:
    """No delivery is configured. The services check ``Settings.email_enabled`` first, so this
    only runs if a caller forgets to; it fails loudly instead of pretending to send."""

    name = "none"

    def send(self, message: EmailMessage) -> None:
        raise EmailDeliveryError("No e-mail backend is configured (EMAIL_BACKEND)")


def build_email_sender(settings: Settings) -> EmailSender:
    backend = settings.effective_email_backend
    if backend == "smtp":
        if settings.smtp_host is None or settings.email_from is None:  # Settings validates this
            raise RuntimeError("EMAIL_BACKEND=smtp requires SMTP_HOST and EMAIL_FROM")
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            sender=settings.email_from,
            username=settings.smtp_username,
            password=settings.smtp_password.get_secret_value() if settings.smtp_password else None,
            security=settings.smtp_security,
            timeout_seconds=settings.smtp_timeout_seconds,
        )
    if backend == "console":
        return ConsoleEmailSender()
    if backend == "memory":
        return MemoryEmailSender()
    return DisabledEmailSender()


def deliver(sender: EmailSender, message: EmailMessage) -> bool:
    """Send in the background after the response; log (never raise) on failure.

    The log line carries the purpose and the sender, never the recipient or the body, so a failed
    delivery cannot leak an address or a one-time link into the logs.
    """
    try:
        sender.send(message)
    except EmailDeliveryError as exc:
        logger.error(
            "email.delivery_failed purpose=%s backend=%s error=%s",
            message.purpose,
            sender.name,
            exc,
        )
        return False
    return True
