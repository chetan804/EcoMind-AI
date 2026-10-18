# ML evaluation protocol

Applies to every capability in `ml/`. A model may be exposed to users only after its evaluation report and model card exist and were reviewed.

## Common rules
1. **Data provenance first:** the dataset has a manifest in `datasets/manifests/` (source, licence, collection period, size, hashes, label mapping, personal-data statement). Unlicensed or unknown-provenance data is not used.
2. **Splits are defined before modelling** and stored in the manifest/config: train / validation / test. The test split is used once per candidate for the final report, never for tuning. Near-duplicates (same scene, same photographer/session) must not straddle splits.
3. **Reproducibility:** fixed random seeds, configuration in `ml/configs`, dependency versions and code commit recorded in the registry manifest.
4. **Baselines:** every learned model is compared against a simple baseline; adoption requires beating it on the validation protocol with stated margin.
5. **Reporting:** metrics with sample sizes, per-class/per-segment breakdown, known failure modes and limitations. Confidence intervals or repeated runs where feasible.
6. **Model card** (`docs/ml/model-cards/<capability>-<version>.md`): intended use, data, preprocessing, metrics, limitations, ethical/privacy notes, owner, date, artifact hashes.
7. **No unsupported claims:** documentation and UI must not state accuracy or readiness beyond the reported evidence. Simulated data is always labelled and never used to claim real-world performance.

## Waste classification
- **Task:** identified object/product and waste-material category are separate outputs; guidance is not predicted.
- **Metrics:** accuracy, macro-F1, per-class precision/recall, **confusion matrix**, top-k accuracy if top-k is shown, calibration (reliability curve / expected calibration error) for confidence values.
- **Uncertainty:** choose the "needs review" threshold on the validation split to hit a stated precision for auto-accepted predictions; report the review rate.
- **Robustness checks:** lighting, background, partial occlusion, image quality, unseen objects (out-of-distribution rejection rate).
- **Human-review loop:** reviewed corrections are stored with the prediction and become candidate training data only after a quality check; each new training set gets a new manifest version.

## Forecasting
- **Data:** historical observations with consistent UTC timestamps and explicit units (kg), aggregated to the forecast granularity; missing periods handled and documented.
- **Splits:** **chronological** (train on the past, validate on the following period, test on the latest period); no shuffling; rolling-origin evaluation preferred.
- **Baselines:** seasonal naive and moving average.
- **Horizon and metrics:** state the horizon (e.g. 7 days); report MAE, RMSE and sMAPE per horizon step and against the baselines; prediction interval coverage if intervals are shown.

## Anomaly detection
- **Definition:** metrics, aggregation window and thresholds are written down before evaluation (`ml/configs`).
- **Baseline:** documented statistical rule (robust z-score / rolling median deviation).
- **Validation:** known historical incidents when they exist; otherwise explicitly labelled simulated anomalies injected into real or synthetic series. Report precision, recall, false-alarm rate per period and detection delay.
- **Severity and explanation:** severity mapping is a documented function of deviation size/persistence; every alert includes observed vs expected values and a plain-language reason.

## Artifact loading
Artifacts live outside Git under `MODEL_ARTIFACTS_DIR`, are described by a manifest in `ml/model_registry`, and are verified by SHA-256 before loading. The backend records the active model name/version with every prediction.
