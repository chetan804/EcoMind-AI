# Readable, non-destructive developer commands. Run `make help`.
# Nothing here deletes volumes, databases or data (no `down -v`, no database reset).

PYTHON ?= python3
BACKEND_VENV := backend/.venv
VENV_BIN := $(abspath $(BACKEND_VENV))/bin
TEST_DATABASE_URL ?= postgresql+psycopg://ecomind:$(shell grep -E '^POSTGRES_PASSWORD=' .env 2>/dev/null | cut -d= -f2)@localhost:5432/postgres

.DEFAULT_GOAL := help
.PHONY: help env setup install-backend install-frontend install-e2e db-up up down logs migrate \
        migration backend-dev frontend-dev lint typecheck test test-backend test-backend-unit \
        test-frontend test-ml test-contract test-e2e check compose-config build-frontend data-dictionary

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "} {printf "  %-22s %s\n", $$1, $$2}'

env: ## Create .env files from the templates (never overwrites) and generate secrets
	$(PYTHON) scripts/setup/init_env.py

setup: env install-backend install-frontend ## First-time setup: env files + dependencies

install-backend: ## Create backend/.venv and install backend + ML dev dependencies
	$(PYTHON) -m venv $(BACKEND_VENV)
	$(VENV_BIN)/pip install -e "backend[dev]" -r ml/requirements-dev.txt

install-frontend: ## Install frontend dependencies from the lockfile
	cd frontend && npm ci

install-e2e: ## Install Playwright and Chromium for end-to-end tests
	cd tests/e2e && npm ci && npx playwright install --with-deps chromium

db-up: ## Start only PostgreSQL (docker compose)
	docker compose up -d --wait db

up: ## Start the full stack: db -> migrations -> backend -> frontend
	docker compose up -d --build --wait

down: ## Stop the stack (keeps the database volume)
	docker compose down

logs: ## Follow logs of all services
	docker compose logs -f

migrate: ## Apply database migrations to DATABASE_URL (backend/.env)
	cd backend && $(VENV_BIN)/alembic upgrade head

migration: ## Autogenerate a migration: make migration m="add widgets"
	@test -n "$(m)" || (echo 'usage: make migration m="message"' && exit 1)
	cd backend && $(VENV_BIN)/alembic revision --autogenerate -m "$(m)"

backend-dev: ## Run the API on the host with auto-reload (http://localhost:8000)
	cd backend && $(VENV_BIN)/uvicorn app.main:create_app --factory --reload --port 8000

frontend-dev: ## Run the frontend dev server (http://localhost:5173)
	cd frontend && npm run dev

lint: ## Lint and format-check backend, ML and frontend
	cd backend && $(VENV_BIN)/ruff check . && $(VENV_BIN)/ruff format --check .
	cd ml && $(VENV_BIN)/ruff check . && $(VENV_BIN)/ruff format --check .
	cd frontend && npm run lint

typecheck: ## Type-check backend (mypy), ML (mypy) and frontend (tsc)
	cd backend && $(VENV_BIN)/mypy
	cd ml && $(VENV_BIN)/mypy
	cd frontend && npm run typecheck

test-backend-unit: ## Backend tests that need no database
	cd backend && $(VENV_BIN)/pytest -m "not integration"

test-backend: ## All backend tests (integration tests need TEST_DATABASE_URL, see runbook)
	cd backend && TEST_DATABASE_URL="$(TEST_DATABASE_URL)" $(VENV_BIN)/pytest

test-frontend: ## Frontend unit, component and integration tests
	cd frontend && npm test

test-ml: ## ML preprocessing/inference tests
	cd ml && $(VENV_BIN)/pytest

test-contract: ## API contract tests (OpenAPI vs documented/consumed contract)
	$(VENV_BIN)/pytest tests/contract

test-e2e: ## Playwright tests against the running stack (E2E_BASE_URL)
	cd tests/e2e && npx playwright test

test: test-backend test-frontend test-ml test-contract ## Everything except e2e

check: ## Repository-level checks: structure and environment templates
	$(PYTHON) scripts/quality/check_structure.py
	$(PYTHON) scripts/quality/check_env_templates.py

compose-config: ## Validate compose.yaml (uses .env.example values if .env is missing)
	docker compose --env-file $$( [ -f .env ] && echo .env || echo .env.example ) config --quiet

build-frontend: ## Production build of the frontend
	cd frontend && npm run build

data-dictionary: ## Regenerate docs/database/data-dictionary.md from the models
	$(VENV_BIN)/python scripts/database/generate_data_dictionary.py
