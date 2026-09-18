# IoT Architecture

Smart-bin records currently provide a database-ready foundation for bin code, location, fill level, battery, status, and last-seen time. Live MQTT ingestion, device authentication, telemetry processing, alert rules, time-series storage, and a simulator are not active.

Future ingestion must preserve provenance and label synthetic data as demo/simulated. Production dashboards must distinguish observed, estimated, calculated, predicted, and simulated values.
