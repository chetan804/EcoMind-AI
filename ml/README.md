# ML

Model training, evaluation and inference code for EcoMind AI. It is **separate from the API**: the backend never trains models, and nothing here imports `backend/app`. The backend calls the `inference/` code of a capability through the owning module's service (for example `backend/app/modules/classification`).

**Status:** one model exists: the waste *material* classifier `1.0.0` (candidate; TrashNet only; see `waste_classification/README.md`, its model card and evaluation report). Shared code: image preprocessing (`common/preprocessing`) and classification metrics (`common/evaluation`). Forecasting and anomaly detection have no models yet. Nothing in this repository may claim a model is accurate or production-ready beyond the evidence stored under `docs/ml/`.

## Layout
| Path | Responsibility |
|---|---|
| `common/config/` | Loading and validating per-capability configuration from `configs/` (added with the first training pipeline). |
| `common/preprocessing/` | Preprocessing shared by training and inference. Implemented: `images.py`. |
| `common/evaluation/` | Shared metrics and reporting helpers (added with the first evaluation). |
| `waste_classification/` | Image classification: `data/` (local only, ignored by Git), `training/`, `evaluation/`, `inference/`, `experiments/`. |
| `forecasting/` | Waste-generation forecasting; same sub-layout. |
| `anomaly_detection/` | Operational anomaly detection; same sub-layout. |
| `model_registry/` | Versioned artifact **manifests** (small, tracked): model name, version, artifact hashes, dataset manifest, metrics, code commit. |
| `artifacts/` | Generated model files. **Ignored by Git** (only `.gitkeep` is tracked). |
| `configs/` | Tracked, reviewable YAML configuration (sizes, seeds, split definitions, thresholds). |
| `notebooks/` | Exploration only. Notebooks never feed production; findings that matter move into code and docs. |
| `tests/` | Preprocessing and inference tests (added alongside the ML package layout; not part of the original tree). |

## Rules
1. Each capability documents its input/output contract, preprocessing configuration, model version, evaluation protocol and artifact-loading strategy in its own README and in `docs/ml/`.
2. Training must be reproducible: fixed seeds, configuration in `configs/`, dataset identified by a manifest in `datasets/manifests/`, code commit recorded in the registry manifest.
3. Evaluate on a held-out test split that is never used for tuning; forecasting uses chronological splits. See `docs/ml/evaluation-protocol.md`.
4. Inference exposes uncertainty (confidence, "unknown/needs review" below a threshold). Only values the deployed model actually produces may be shown to users.
5. Artifacts are located through `MODEL_ARTIFACTS_DIR` and verified against their registry manifest before loading.
6. Never commit private data, large raw datasets, credentials or model files.

## Framework selection
scikit-learn and/or PyTorch are chosen per capability once the data and accuracy needs are known, and recorded in an ADR. Until then `ml/requirements.txt` lists only Pillow, so installing stays small. `ml/` is a code directory (importable as `ml.*` from the repository root), not an installable package.

## Commands
```bash
make install-backend   # installs backend and ml dev dependencies (ml/requirements-dev.txt) into backend/.venv
make test-ml           # pytest for ml/
```
