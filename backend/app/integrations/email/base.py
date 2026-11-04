"""The e-mail boundary: a message, a sender protocol and one delivery error."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmailMessage:
    """A plain-text message. ``purpose`` is for logs only (never contains secrets)."""

    to: str
    subject: str
    body: str
    purpose: str


class EmailDeliveryError(Exception):
    """The message could not be handed to the mail server (the cause is chained).

    ``transient`` is True for failures that may succeed on a later attempt (network error, timeout,
    server disconnect, 4xx reply). Rejected recipients, authentication failures, 5xx replies and
    configuration problems are permanent and are never retried.
    """

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


class EmailSender(Protocol):
    name: str

    def send(self, message: EmailMessage) -> None:
        """Deliver ``message`` or raise :class:`EmailDeliveryError`."""
        ...
