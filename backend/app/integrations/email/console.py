"""Development backends: write to the log, or keep messages in memory for tests."""

from __future__ import annotations

import logging

from app.integrations.email.base import EmailMessage

logger = logging.getLogger("app.email.console")


class ConsoleEmailSender:
    """Writes the whole message (including any one-time link) to the log. Local use only:
    configuration validation refuses this backend in production."""

    name = "console"

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "EMAIL (console backend, development only)\nTo: %s\nSubject: %s\n\n%s",
            message.to,
            message.subject,
            message.body,
        )


class MemoryEmailSender:
    """Collects messages in ``outbox``. Used by the test suite (``ENVIRONMENT=test``)."""

    name = "memory"

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []
        self.fail_with: Exception | None = None

    def send(self, message: EmailMessage) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.outbox.append(message)
