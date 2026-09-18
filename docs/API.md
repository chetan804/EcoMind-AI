# API Surface

The backend currently exposes unversioned routes for compatibility. OpenAPI is available at `/docs` outside production mode.

- `/auth/login`: OAuth2 password-form login.
- `/users`: citizen registration and current profile.
- `/waste-reports`: create and list citizen reports; admin status workflow.
- `/classification/{report_id}`: authenticated report classification.
- `/collections`: admin assignment and collector status workflow.
- `/routes`: route generation and role-scoped route access.
- `/complaints`: internal citizen complaint portal and admin triage.
- `/notifications`: authenticated in-app notifications.
- `/rewards`: authenticated reward balance and activity.
- `/carbon`: sustainability credit balance, marketplace, and transactions.
- `/environmental`: admin environmental sources, readings, and smart-bin records.
- `/analytics`: admin dashboard and waste distribution metrics.
- `/assistant/ask`: authenticated fallback guidance assistant.
- `/liveness`, `/readiness`, `/health`: operational checks.

Authentication uses `Authorization: Bearer <access-token>`. Backend authorization remains authoritative for roles, ownership, and future organization scope.
