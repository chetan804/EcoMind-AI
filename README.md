# EcoMind-AI

**Multi-tenant smart waste management & environmental intelligence platform.**

EcoMind-AI helps municipalities, private waste operators, campuses and communities run
citizen reporting, collection operations, fleet & route optimization, IoT bin monitoring,
complaint resolution and sustainability accounting — on one platform with strict tenant
isolation and honest, fully-traceable data.

> **Demo environment** — a fully seeded demo organization (`aurora-demo`) is included.
> All demo data is machine-labelled (`is_demo`, `is_simulated`) and surfaced with visible
> DEMO / SIMULATED badges in the UI. See [Demo login](#-demo-login).

---

## What's inside

| Area | Highlights |
| --- | --- |
| **Multi-tenant SaaS** | Org-scoped data on every row, enforced by repository filters + automated cross-tenant test suite (release-blocking) |
| **RBAC** | 8 roles (org admin → viewer) with ~50 granular permissions, checked server-side on every request |
| **Auth** | Argon2id hashing, JWT access + rotating refresh tokens with revocation, password reset, per-route rate limits |
| **Citizen experience** | 3-step report wizard (photo, geolocation, AI classification with confidence + human-review path), points & community leaderboard |
| **Operations** | Live command-center map with layers, report triage, complaints with SLA + comments, collection events, fleet, IoT devices & threshold alerts |
| **Routing** | OR-Tools capacitated VRP (stop sequencing) cleanly separated from road geometry (OSRM adapter with labelled straight-line fallback) |
| **Field app** | Touch-first route execution: per-stop weights, contamination flags, skip reasons |
| **IoT** | Device registry with per-device API keys, authenticated ingestion, configurable alert rules, explicitly-labelled telemetry simulator |
| **AI** | Provider-independent abstraction (OpenAI / Anthropic / Google / deterministic baseline). No fabricated results: the fallback labels every inference `is_simulated` and routes low-confidence output to human review |
| **Sustainability** | Versioned emission-factor library, measured/estimated/modeled quality labels, carbon records with full provenance, no tradable "carbon credits" |
| **Analytics** | Role-specific dashboards (ops / citizen / sustainability / executive) computed only from real underlying rows; CSV exports |
| **Platform** | Audit log, structured errors with request IDs, PG-backed job queue, storage abstraction, Docker deployment, CI |

## Quick start (local development)

Prereqs: **Python 3.11+**, **Node 20+**, and the bundled dev PostgreSQL (via `pgserver`,
no system Postgres needed).

```bash
# 1. Backend
cd backend
python3 -m venv venv
./venv/bin/pip install -e ".[dev]"
cp .env.example .env                 # then edit ECOMIND_SECRET_KEY
./venv/bin/python scripts/dev_pg.py &  # boots bundled PostgreSQL at .pgdata
./venv/bin/alembic upgrade head
./venv/bin/uvicorn app.main:app --reload   # http://localhost:8000/docs

# 2. Demo data (re-runnable)
./venv/bin/python scripts/seed_demo.py --reset

# 3. Frontend
cd ../frontend
npm install
npm run dev                          # http://localhost:5173 (proxies /api → :8000)
```

### Demo login

| Account | Role |
| --- | --- |
| `admin@aurora.demo` | Organization admin |
| `ops@aurora.demo` | Operations manager |
| `supervisor@aurora.demo` | Field supervisor |
| `driver1@aurora.demo` | Collector / driver |
| `analyst@aurora.demo` | Sustainability analyst |
| `citizen1@aurora.demo` … `citizen15@` | Citizens |

Password for all demo accounts: **`EcoDemo2026!`** (quick-fill buttons on the login page).

## Docker deployment

```bash
cp backend/.env.example backend/.env   # set ECOMIND_SECRET_KEY + POSTGRES_PASSWORD
docker compose up --build              # frontend on http://localhost:8080
```

Full instructions: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Tests

```bash
cd backend  && ./venv/bin/pytest -q      # 51 tests incl. tenant-isolation suite
cd frontend && npm test                  # 22 vitest tests
cd frontend && npm run typecheck && npm run build
```

CI runs backend lint + tests against a real PostgreSQL service, frontend
typecheck + tests + build, and Docker image builds on every push/PR.

## Documentation

| Doc | Contents |
| --- | --- |
| [docs/PRODUCT.md](docs/PRODUCT.md) | Personas, journeys, feature catalogue |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, domains, data model, isolation model |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Dev environment, conventions, testing, seeding |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, configuration reference, scaling |
| [docs/SECURITY.md](docs/SECURITY.md) | Threat model, authn/z, tenant isolation, headers |
| [docs/PRIVACY.md](docs/PRIVACY.md) | Data categories, retention, citizen privacy |
| [docs/API.md](docs/API.md) | Endpoint map, conventions, error model |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Runbooks, jobs, alerts, backups |
| [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) | Honest list of what is not done |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Prioritized future work |
| [docs/adr/](docs/adr/) | Architecture decision records |

## Honest labelling policy

Every capability in EcoMind-AI is one of: **implemented**, **simulated** (labelled),
**integration-ready** (adapter exists, provider not bundled), or **future** (roadmap).
Nothing is faked: AI results without a configured provider are marked `is_simulated`,
estimated route geometry is flagged per-route, and avoided emissions are kept separate
from measured totals. See [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md).

## License

Provided as-is for evaluation. All rights reserved by the repository owner.
