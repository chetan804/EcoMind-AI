# Project scope

## Purpose
EcoMind AI is an AI-powered waste-intelligence, waste-management-operations and circular-economy platform.

## In scope (product)
Authentication and access control; user/role administration; waste reports with images; image-based object recognition and waste-material classification with sorting guidance; collection tasks, assignments and events; route planning; facilities and fleet; circular-economy records with verified recovery; dashboard analytics; waste-generation forecasting; operational anomaly detection; community incidents; material passports and chain of custody; rewards and impact ledger; notifications; audit and administration.

## Status of the scope
The foundation milestone (repository structure, locked stack, configuration, schema, shells, CI, local containers) is complete and every product area above has been built: see `docs/requirements/functional-requirements.md` (per-requirement status and test evidence) and `docs/project-completion/IMPLEMENTATION_STATUS.md`. Two items of the product scope are **not** delivered as described: image-based *object* recognition (the classifier predicts material category only, and no model is active or release-approved) and live vehicle positions from a real GPS source (only the ingestion path, a labelled simulator and stored positions exist). The release target is a supervised demonstration or academic submission, not public production.

## Out of scope (until a requirement is accepted)
Physical IoT hardware and live sensor telemetry (the `integrations/sensors` boundary exists but nothing is exposed); mobile native apps; payment or monetary rewards; multi-tenant/organization hierarchy; real-time messaging; third-party marketplace integrations; any claim of trained or production-ready ML models.

## Users (roles to be defined in the authentication milestone)
Citizens (reporting, sorting guidance, rewards), collectors/drivers (tasks, routes), facility operators (recovery, custody), operations managers (planning, analytics, alerts), administrators (users, audit). The role/permission catalogue is data in `roles`/`permissions` and will be seeded when authorization is implemented.

## Assumptions and constraints
Single-region deployment; one PostgreSQL database; uploaded media on persistent storage; ML models trained only on datasets whose licence and provenance are recorded; privacy by default (no personal data in datasets or logs).
