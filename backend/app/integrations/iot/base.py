from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class IoTUnavailable(RuntimeError):
    """Raised when an IoT broker or device adapter is unavailable."""


@dataclass(frozen=True)
class SensorReading:
    device_id: str
    fill_level: float
    battery_level: float
    recorded_at: datetime
    source: str
    simulated: bool = False


class IoTAdapter(Protocol):
    def publish(self, reading: SensorReading) -> None:
        """Publish a sensor reading to the configured gateway."""
