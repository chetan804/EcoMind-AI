"""Choose the e-mail backend from settings (``EMAIL_BACKEND``) and deliver safely."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

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


MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (0.5, 2.0)  # waits before attempt 2 and 3


def deliver(
    sender: EmailSender,
    message: EmailMessage,
    *,
    max_attempts: int = MAX_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Send in the background after the response; log (never raise) on failure.

    A transient failure (network error, timeout, 4xx reply) is retried with a short backoff, up to
    ``max_attempts`` in total; a permanent one (refused recipient, authentication, 5xx) is not.
    It runs on a worker thread after the response, so waiting never delays the person.

    The log lines carry the purpose, the backend and the attempt count, never the recipient or the
    body, so a failed delivery cannot leak an address or a one-time link into the logs. A caller
    that needs durable retry across restarts needs an outbox table, which does not exist yet.
    """
    attempt = 0
    while True:
        attempt += 1
        try:
            sender.send(message)
        except EmailDeliveryError as exc:
            if exc.transient and attempt < max_attempts:
                logger.warning(
                    "email.delivery_retry purpose=%s backend=%s attempt=%d error=%s",
                    message.purpose,
                    sender.name,
                    attempt,
                    exc,
                )
                sleep(BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)])
                continue
            logger.error(
                "email.delivery_failed purpose=%s backend=%s attempts=%d transient=%s error=%s",
                message.purpose,
                sender.name,
                attempt,
                exc.transient,
                exc,
            )
            return False
        logger.info(
            "email.delivered purpose=%s backend=%s attempts=%d",
            message.purpose,
            sender.name,
            attempt,
        )
        return True
