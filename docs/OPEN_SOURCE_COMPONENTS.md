# Open-Source Components and AI Integrations

This document records the current implementation status. The project does not claim an external model or service is active until its dependency, license, configuration, and runtime availability are verified.

| Component | Purpose | Version | License | Source | Current status |
|---|---|---:|---|---|---|
| FastAPI | REST API framework | 0.141.1 | MIT | https://github.com/fastapi/fastapi | Active |
| SQLAlchemy | ORM and database access | 2.0.52 | MIT | https://github.com/sqlalchemy/sqlalchemy | Active |
| Alembic | Database migrations | 1.19.1 | MIT | https://github.com/sqlalchemy/alembic | Active |
| React | Frontend UI | 19.2.8 | MIT | https://github.com/facebook/react | Active |
| Vite | Frontend build tool | 8.2.2 | MIT | https://github.com/vitejs/vite | Active |
| Keyword waste classifier | Deterministic baseline fallback | 1.0.0 | Internal project logic | `backend/app/ai/waste_classifier.py` | Active |
| Keyword complaint analyzer | Deterministic recommendation baseline | 1.0.0 | Internal project logic | `backend/app/ai/complaint_analyzer.py` | Active |
| Ollama | Optional local assistant provider | Not installed | Verify per selected model | https://github.com/ollama/ollama | Configuration-ready, inactive |
| Hugging Face Transformers | Optional ML classifier provider | Not installed | Verify per selected model | https://github.com/huggingface/transformers | Planned adapter |
| PyTorch | Optional model runtime | Not installed | BSD-style | https://github.com/pytorch/pytorch | Planned adapter |
| OR-Tools | Optional route optimization solver | Not installed | Apache-2.0 | https://github.com/google/or-tools | Planned adapter |
| OSRM | Optional road-network routing | External service not configured | BSD-2-Clause | https://github.com/Project-OSRM/osrm-backend | Planned adapter |

## AI Traceability

The current baseline stores model name, model version, provider, confidence, timestamp, and inference latency for waste classification. Complaint analysis stores its recommendation and model metadata. AI operation summaries are recorded in `ai_operation_logs` without raw credentials or tokens.

## Selection Policy

Before enabling an external model or service:

1. Verify the exact release and compatible Python/runtime versions.
2. Inspect the model or project license and attribution requirements.
3. Evaluate model size and CPU/GPU requirements.
4. Record the selected name, revision, source, and license here.
5. Add a controlled adapter and a fallback path.
6. Add tests for unavailable providers and invalid model output.

The keyword implementations are baselines and must not be described as deep-learning inference.
