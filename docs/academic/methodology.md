# Methodology

## 1. Architecture
A modular monolith (decision record: `docs/decisions/ADR-0001-modular-monolith.md`). React 19 and
TypeScript single-page app; FastAPI under `/api/v1`; PostgreSQL 16 with SQLAlchemy 2 and Alembic (nine
migrations, head `0009`); an isolated `ml/` package for training, evaluation and inference code, kept out
of request handlers. Diagrams and tables: `docs/architecture/`, `docs/database/er-diagram.md`,
`docs/database/data-dictionary.md`. No message broker, cache server or PostGIS is used because no verified
requirement needs one.

## 2. Security design
Argon2id passwords; 15-minute bearer access tokens held in memory; rotating HttpOnly refresh cookie with
reuse detection; per-email and per-address lockout derived from the append-only audit log; deny-by-default
RBAC with permissions re-read from the database on every request; optional TOTP MFA with recovery codes;
validated, re-encoded image uploads. Controls and review: `docs/security/`. Every route's required
permission is listed in `docs/security/route-permission-matrix.md` and guarded by a test.

## 3. Material classification
- **Data.** TrashNet (six classes, MIT) for training. Splits are made by *group* (near-identical photos of
  one item stay together: 1,477 groups, train/validation/test = 1,684/422/421) so that the test split cannot
  contain a near-duplicate of a training image. RealWaste (CC BY-NC-SA 4.0) is used only for cross-dataset
  evaluation and an experiment.
- **Model.** A frozen EfficientNet-EdgeTPU TFLite backbone gives L2-normalised features; a regularised
  multinomial logistic head is trained on them. The backbone is not fine-tuned (no GPU or deep-learning
  framework is available in the build environment, so this is a stated limitation, not a design preference).
- **Calibration and abstention.** Temperature scaling on the validation split; a prediction is sent to human
  review when its calibrated confidence is below a threshold or its feature similarity to the training data
  (a novelty check) is too low. Hyper-parameters, the threshold and the temperature are chosen on
  train/validation only; the test split is scored once.
- **Reproducibility.** The command, dataset manifest (with SHA-256), configuration and model hashes are
  committed (`docs/ml/reports/`, `ml/model_registry/`); the 1.0.0 model was re-trained and matched
  bit-for-bit (`docs/ml/dataset-research/experiments/reproducibility-1.0.0.md`). The classifier verifies
  file hashes at load and refuses a tampered artifact.
- **Cross-dataset and multi-dataset study.** The released model is scored on RealWaste's six shared
  classes; separate experiments train on TrashNet, RealWaste, and both, with and without class balancing,
  and report each model on both datasets' held-out splits (`docs/ml/dataset-research/DATASET_SELECTION_REPORT.md`).

## 4. Forecasting and anomaly detection
Weekly series (platform-collected weight, plus two public reference series) with chronological splits.
Candidate algorithms are scored against naive baselines by mean absolute error on a held-out final segment
(`docs/ml/dataset-research/experiments/time-series-results.json`); the forecaster refuses to answer with
fewer than 26 weeks of history (`422 insufficient_history`). Anomalies use a robust z-score against a median baseline (the same week in previous years when enough
history exists, otherwise the previous three weeks), with documented thresholds (3.5 warning, 5 critical); the data carry no incident labels, so **no precision or recall is
claimed**, and alerts are called "suspected anomalies".

## 5. Route ordering
Exact Held-Karp for up to 12 stops; above that, nearest-neighbour followed by 2-opt and Or-opt, seeded
for determinism; at most 40 tasks per plan; straight-line (haversine) distance, no travel-time estimate.
Validated on the public King Saud University routing instances (CC BY 4.0).

## 6. Impact and rewards
Points = round(weight in kg × 10) for a task that came from a verified citizen report, once per user and
task. No emission or energy coefficient is used because none has been sourced; the system shows recovered
weight, which is measured.

## 7. Quality assurance
Backend tests against real PostgreSQL (including migration round trips and constraint tests), frontend
unit/integration tests, ML tests, contract tests, a Playwright end-to-end core workflow, and **mutation
checks**: for each module a rule was deliberately broken to confirm a test fails. Static checks: ruff,
mypy (strict for ML), ESLint, TypeScript. CI runs these on every push (`.github/workflows/`).
