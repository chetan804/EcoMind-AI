# Testing

## Backend

Run from `backend` with the project virtual environment:

```powershell
$env:ENVIRONMENT='development'
$env:SECRET_KEY='development-only-secret-value-for-tests-1234567890'
$env:DATABASE_URL='sqlite:///./test-placeholder.db'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app alembic tests
```

The current suite covers foundation configuration/health behavior, baseline AI behavior, authorization helpers, lifecycle transitions, rewards/carbon services, municipality summaries, and the OSRM adapter. PostgreSQL migration and endpoint integration tests require a running PostgreSQL test database.

## Frontend

```powershell
cd frontend
npm run build
npm run lint
```

## Release gate

A release requires passing backend tests, backend compilation, frontend build/lint, migration validation, PostgreSQL integration tests, security tests, and a manual citizen, collector, and admin workflow review.
