# Integration: Sensors

Future-capable adapter boundary for IoT/sensor telemetry. **No physical hardware is assumed and no sensor tables exist.** Sensor data must not be shown in the main navigation or presented as live data unless real devices are connected. Tables (`sensor_devices`, `sensor_readings`) are added by a migration only when a documented requirement exists.

**Status:** boundary defined only; nothing implemented.

Rules: integrations are called by module services, never by routers directly; they hold no business rules and no database tables of their own unless stated above.
