# Testing strategy

Principles: test behaviour at the cheapest layer that can prove it; no empty or permanently skipped tests; never weaken or delete a test to get green; tests never touch shared databases or real secrets.

| Layer | Location | Tooling | What it proves | Command | Runs in CI |
|---|---|---|---|---|---|
| Backend unit | `backend/tests/unit` | pytest | config validation, pagination, permissions, logging | `make test-backend-unit` | backend-ci |
| Backend API | `backend/tests/api` | pytest + TestClient | routes, error envelope, request ids, CORS, health/ready, docs gating | `make test-backend` | backend-ci |
| Auth & authorization | `backend/tests/security` | pytest | password hashing, token validation (tampering, expiry, alg=none, wrong issuer/type), later: per-endpoint permission matrix | `make test-backend` | backend-ci |
| Database integration | `backend/tests/integration` | pytest + Alembic + PostgreSQL | upgrade/downgrade, model/migration drift, naming, FK indexes, constraints, readiness against a real DB | `make test-backend` (needs `TEST_DATABASE_URL`) | backend-ci (PostgreSQL 16 service) |
| ML | `ml/tests` | pytest | preprocessing and (later) inference contracts | `make test-ml` | quality-gates |
| Frontend unit | `frontend/tests/unit` | Vitest | API client, error handling, config, form stack | `make test-frontend` | frontend-ci |
| Frontend component | `frontend/tests/components` | Vitest + React Testing Library | components in loading/success/error states (role queries) | same | frontend-ci |
| Frontend integration | `frontend/tests/integration` | Vitest + RTL + memory router | routing and feature flows with a stubbed `fetch` | same | frontend-ci |
| API contract | `tests/contract` | pytest | OpenAPI conventions; backend↔frontend schema agreement | `make test-contract` | quality-gates |
| End-to-end | `tests/e2e` | Playwright (Chromium) | real browser against the Compose stack | `make test-e2e` | quality-gates (`e2e`) |
| Smoke | `tests/smoke/smoke.py` | stdlib | `/health`, `/ready`, frontend shell on a running stack | script | quality-gates (`e2e`) |
| Static quality | — | ruff, mypy (strict), ESLint, tsc | style, types, deep-import rule | `make lint typecheck` | all |
| Repository | `scripts/quality` | Python | canonical structure, no secrets in templates, data dictionary current | `make check` | quality-gates |

## Database test isolation
`backend/tests/fixtures/database.py` takes `TEST_DATABASE_URL` (a PostgreSQL server where the role may `CREATE DATABASE`), creates `ecomind_test_<random>` per test, migrates with Alembic, and drops it afterwards with `WITH (FORCE)`. The database named in the URL is only used for CREATE/DROP and is never modified. Without `TEST_DATABASE_URL`, integration tests are **skipped with an explicit reason**; CI always provides it, and when the `CI` environment variable is set a missing `TEST_DATABASE_URL` makes those tests **fail** instead of skip, so CI cannot pass with the database layer silently uncovered.

## Conventions for new features
1. Service rules: unit tests with an isolated database where persistence matters.
2. Every endpoint: API tests (success, validation error, not found, conflict) and security tests (unauthenticated → 401, wrong role → 403, own-vs-other resource).
3. Every table constraint: a failing-insert test in `test_schema_constraints.py` (or a module-specific integration test).
4. Every screen: component tests for loading, empty, error and success states; one Playwright test per critical user workflow.
5. ML: preprocessing and inference tests with small generated fixtures (no real data in the repository); evaluation reports are artifacts, not unit tests.
6. Test fixtures and demonstration data live only in test directories or explicitly labelled demo seeds.
