# Disaster Recovery

PostgreSQL is the system of record and is persisted through the Compose `postgres_data` volume in local deployments.

Before production launch, the operator must define backup frequency, retention, encryption, recovery point objective, recovery time objective, off-site storage, and restoration ownership. A restore drill must be performed against a non-production database before declaring the deployment recoverable.

Application recovery sequence:

1. Restore PostgreSQL backup.
2. Start the database and verify health.
3. Run `alembic upgrade head`.
4. Start the API and verify `/readiness`.
5. Start the frontend and verify authentication and critical workflows.
6. Review logs, request IDs, and data integrity.
