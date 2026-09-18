from dataclasses import dataclass
from typing import Protocol


class AIUnavailable(RuntimeError):
    """Raised when an external AI provider is not configured or available."""


@dataclass(frozen=True)
class AIResult:
    label: str
    confidence: float
    model: str
    provider: str
    fallback: bool = False


class AIAdapter(Protocol):
    def classify(self, text: str) -> AIResult:
        """Classify untrusted text using a configured provider."""
