from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class Prediction:
    label: str
    confidence: float
    model_name: str
    model_version: str
    provider: str
    created_at: datetime
    inference_time_ms: float


@dataclass(frozen=True)
class ComplaintAnalysis:
    category: str
    priority: str
    keywords: list[str]
    confidence: float
    model_name: str
    model_version: str
    provider: str
    created_at: datetime
    inference_time_ms: float


class BaseWasteClassifier(Protocol):
    def predict(self, description: str) -> Prediction:
        """Return a validated waste prediction."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
