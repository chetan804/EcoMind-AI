# Cross-application tests

Tests that span the frontend and backend. Tests that belong to one application live with it (`backend/tests`, `frontend/tests`, `ml/tests`); see `docs/testing/testing-strategy.md`.

| Directory | Purpose | Run |
|---|---|---|
| `e2e/` | Playwright browser tests against a running stack (frontend + backend + migrated PostgreSQL). | `make install-e2e`, start the stack, `make test-e2e`. The core-workflow spec also needs `E2E_ADMIN_EMAIL` and `E2E_ADMIN_PASSWORD` (an administrator made with `python -m app.cli create-admin`; CI does this) and fails without them. |
| `contract/` | Checks the backend's generated OpenAPI document against the documented conventions and against what the frontend consumes. Needs the backend venv only (no database). | `make test-contract` |
| `smoke/` | `smoke.py`: post-deploy/startup check of `/health`, `/ready` and the frontend. | `python tests/smoke/smoke.py --api http://localhost:8000 --web http://localhost:5173 --wait 60` |
