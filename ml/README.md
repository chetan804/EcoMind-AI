# ML

Model training, evaluation and inference code for EcoMind AI. It is **separate from the API**: the backend never trains models, and nothing here imports `backend/app`. The backend calls the `inference/` code of a capability through the owning module's service (for example `backend/app/modules/classification`).

**Status:** one model exists: the waste *material* classifier `1.0.0` (candidate; TrashNet only; see `waste_classification/README.md`, its model card and evaluation report). Shared code: image preprocessing (`common/preprocessing`) and classification metrics (`common/evaluation`). Forecasting and anomaly detection are statistical algorithms in `time_series/` (no trained model files); they are evaluated against naive baselines on public series. Nothing in this repository may claim a model is accurate or production-ready beyond the evidence stored under `docs/ml/`.

## Layout
| Path | Responsibility |
|---|---|
| `common/config/` | Loading and validating per-capability configuration from `configs/`. |
| `common/preprocessing/` | Preprocessing shared by training and inference. Implemented: `images.py`. |
| `common/evaluation/` | Shared metrics and reporting helpers (accuracy, macro-F1, calibration error, bootstrap intervals). |
| `waste_classification/` | Image classification: `data/` (local only, ignored by Git), `training/`, `evaluation/`, `inference/`, `experiments/`. |
| `time_series/` | Forecasting algorithms (naive, exponential smoothing, Holt-Winters), robust-score anomaly detection, public-series loading and the benchmark. Used by the backend through `backend/app/modules/forecasting/engine.py`. |
| `forecasting/` | Contract and pointer to `time_series/`; the empty sub-folders exist only for the canonical structure check. |
| `anomaly_detection/` | Contract and pointer to `time_series/`; same note. |
| `model_registry/` | Versioned artifact **manifests** (small, tracked): model name, version, artifact hashes, dataset manifest, metrics, code commit. |
| `artifacts/` | Generated model files. **Ignored by Git** (only `.gitkeep` is tracked). |
| `configs/` | Tracked, reviewable YAML configuration (sizes, seeds, split definitions, thresholds). |
| `notebooks/` | Exploration only. Notebooks never feed production; findings that matter move into code and docs. |
| `tests/` | 61 tests: preprocessing, metrics, classifier, data loaders, time series, dataset research. |

## Rules
1. Each capability documents its input/output contract, preprocessing configuration, model version, evaluation protocol and artifact-loading strategy in its own README and in `docs/ml/`.
2. Training must be reproducible: fixed seeds, configuration in `configs/`, dataset identified by a manifest in `datasets/manifests/`, code commit recorded in the registry manifest.
3. Evaluate on a held-out test split that is never used for tuning; forecasting uses chronological splits. See `docs/ml/evaluation-protocol.md`.
4. Inference exposes uncertainty (confidence, "unknown/needs review" below a threshold). Only values the deployed model actually produces may be shown to users.
5. Artifacts are located through `MODEL_ARTIFACTS_DIR` and verified against their registry manifest before loading.
6. Never commit private data, large raw datasets, credentials or model files.

## Frameworks
Serving needs only NumPy, Pillow and LiteRT (`ai-edge-litert`): the classifier is a frozen TFLite backbone plus a NumPy linear head. scikit-learn, PyYAML and Matplotlib are used for training and evaluation only and are never installed in the API image (`ml/requirements.txt`). No deep-learning framework (PyTorch, TensorFlow) is used, because none is available in the build environment; the consequence is that backbones are not fine-tuned. `ml/` is a code directory (importable as `ml.*` from the repository root), not an installable package.

## Commands
```bash
make install-backend   # installs backend and ml dev dependencies (ml/requirements-dev.txt) into backend/.venv
make test-ml           # pytest for ml/ (61 tests)
```
Reproduce the candidate classifier (needs network access to GitHub; about 10 minutes on 2 CPUs): `PYTHONPATH=. python -m ml.waste_classification.data.fetch`, then `…training.train`, then `…evaluation.report`. These rewrite the tracked report, model card and registry entry (timestamps, commit, latency); review the diff before committing. Reproduced on 2026-10-21: accuracy 0.8670, macro-F1 0.8409, ECE 0.0310 and identical weight hashes.
