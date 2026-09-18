import json

from app.integrations.iot.base import IoTAdapter, IoTUnavailable, SensorReading


class MQTTAdapter:
    def __init__(self, broker_url: str, topic_prefix: str = "ecomind/smart-bins"):
        self.broker_url = broker_url
        self.topic_prefix = topic_prefix.rstrip("/")
        self._client = None

    def connect(self) -> None:
        try:
            import paho.mqtt.client as mqtt
        except ImportError as exc:
            raise IoTUnavailable("MQTT support requires paho-mqtt") from exc

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        try:
            self._client.connect(self.broker_url)
            self._client.loop_start()
        except Exception as exc:
            raise IoTUnavailable("MQTT broker is unavailable") from exc

    def publish(self, reading: SensorReading) -> None:
        if self._client is None:
            self.connect()
        payload = json.dumps({
            "device_id": reading.device_id,
            "fill_level": reading.fill_level,
            "battery_level": reading.battery_level,
            "recorded_at": reading.recorded_at.isoformat(),
            "source": reading.source,
            "simulated": reading.simulated,
        })
        result = self._client.publish(f"{self.topic_prefix}/{reading.device_id}", payload)
        if result.rc != 0:
            raise IoTUnavailable("MQTT publish failed")
