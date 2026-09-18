# Contributing

Use the existing modular-monolith structure and preserve public API compatibility where possible.

Before a change:

- Inspect the current model, router, service, and frontend flow.
- Add an Alembic migration for every schema change.
- Avoid hardcoded credentials, role IDs, provider claims, and production URLs.
- Add focused tests for lifecycle, authorization, ownership, and failure behavior.

Before submitting:

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app alembic tests
cd ..\frontend
npm run build
npm run lint
```
