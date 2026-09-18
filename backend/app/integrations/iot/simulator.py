from datetime import datetime, timezone
from random import uniform

from app.integrations.iot.base import SensorReading


class SmartBinSimulator:
    source = "DEMO / SIMULATED DATA"

    def reading(self, device_id: str) -> SensorReading:
        return SensorReading(
            device_id=device_id,
            fill_level=round(uniform(0, 100), 2),
            battery_level=round(uniform(20, 100), 2),
            recorded_at=datetime.now(timezone.utc),
            source=self.source,
            simulated=True,
        )
