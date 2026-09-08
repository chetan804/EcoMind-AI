# EcoMind AI

EcoMind AI is a role-based waste-management platform for citizens, collectors, and municipal administrators. It combines waste reporting, baseline AI classification, collection operations, route optimization, complaints, notifications, analytics, carbon credits, rewards, environmental readings, and smart-bin readiness.

## Architecture

- `backend/`: FastAPI, SQLAlchemy, PostgreSQL, Alembic, JWT, bcrypt
- `frontend/`: React, TypeScript, Vite
- `backend/app/services/`: business rules and replaceable domain services
- `backend/app/ai/`: provider-independent classifiers, complaint analysis, and assistant fallback
- `backend/alembic/versions/`: every database schema change

The classifier is currently a documented deterministic keyword baseline. Route optimization uses a local haversine and nearest-neighbor algorithm. Environmental and smart-bin records are integration-ready data models; they do not claim live hardware connectivity.

AI predictions include model name, version, provider, confidence, timestamp, and inference latency. Complaint analysis is a recommendation for administrator review. The assistant uses an authenticated backend context and a safe local guidance fallback when an optional Ollama provider is unavailable. See [docs/OPEN_SOURCE_COMPONENTS.md](docs/OPEN_SOURCE_COMPONENTS.md) before enabling external models or routing services.

## Local Setup

### Backend

1. Create PostgreSQL database `ecomind_ai`.
2. Copy `backend/.env.example` to `backend/.env` and set real values.
3. Create and activate the virtual environment.
4. Install dependencies:

```powershell
cd backend
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`. Development documentation is at `/docs`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` in `frontend/.env.local` when the API is not running at `http://localhost:8000`.

### Docker Compose

```bash
docker compose up --build
```

This starts PostgreSQL, the backend API, and the frontend UI together. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for full operational details.

## Production Checklist

- Use a unique high-entropy `SECRET_KEY`.
- Set `ENVIRONMENT=production`.
- Set `CORS_ORIGINS` to the deployed frontend origin only.
- Run `alembic upgrade head` before starting the API.
- Run the API behind a TLS-terminating reverse proxy.
- Keep PostgreSQL credentials and `.env` files out of Git.
- Configure backups, monitoring, log aggregation, and database connection limits.
- Build the frontend with `npm run build` and serve `dist/` from a static host or reverse proxy.

## Verification

```powershell
cd backend
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q app alembic tests
cd ..\frontend
npm run build
```

## Current Scope

The backend API and operational frontend foundation are implemented. Remaining product work includes richer admin/collector forms, full end-to-end API tests, and deployment-specific observability and infrastructure configuration.
