# Results

All figures are copied from committed artifacts; the artifact is named in each row. Counts of tests are from
runs on 2026-10-20 unless stated; CI results for the final commit are in
`docs/project-completion/IMPLEMENTATION_STATUS.md`.

## 1. Classifier `waste-classification 1.0.0` (candidate, not activated by default)

Source: `docs/ml/reports/waste-classification-1.0.0.json`, model card
`docs/ml/model-cards/waste-classification-1.0.0.md`.

| Measure (TrashNet held-out test split, n = 421) | Value |
|---|---|
| Accuracy | 0.867 (95% CI 0.813 to 0.912) |
| Macro-F1 | 0.841 |
| Expected calibration error | 0.031 |
| Auto-accepted share / accuracy of those | 73.6% / 96.1% |
| Weakest class | `trash` (F1 0.653) |
| CPU latency, median | 23.1 ms |

Interpretation: on its own benchmark the model is useful and well calibrated. The `trash` class is small
and heterogeneous, which is why it is weakest.

## 2. Cross-dataset generalisation (RealWaste, real facility photographs)

Source: `docs/ml/dataset-research/experiments/cross-dataset-realwaste.json`.

| Measure (in-scope shared classes, n = 3,092) | Value |
|---|---|
| Accuracy | **0.454** (95% CI 0.437 to 0.472) |
| Macro-F1 | 0.514 |
| Expected calibration error | 0.263 |
| Coverage / accuracy of accepted predictions | 36.4% / 55.3% |
| Out-of-scope images (food, textile, vegetation; n = 1,165) sent to review | 95.5% |

Interpretation: **accuracy drops from 0.87 to 0.45 outside the training distribution**, and confidence is no
longer well calibrated. The abstention rule does its job on out-of-scope material (95.5% to review) and keeps
the accepted share more accurate (55.3%), but this is not a field-ready accuracy. The project therefore
makes no field-accuracy claim.

## 3. Multi-dataset experiment (experiment only; frozen backbones; shared six classes)

Source: `experiments/multi-dataset-realwaste.json`; tables in `DATASET_SELECTION_REPORT.md`.
Accuracy ranges across the backbones tried, TrashNet test / RealWaste test:

| Training data | TrashNet test | RealWaste test |
|---|---|---|
| TrashNet only | 0.87 to 0.89 | 0.50 to 0.56 |
| RealWaste only | 0.59 to 0.70 | 0.79 to 0.80 |
| Both | 0.82 to 0.84 | 0.77 to 0.79 |

Confidence intervals are about ±0.05. Class balancing made no significant difference. Training on both
datasets gives the best compromise, but RealWaste is non-commercial (CC BY-NC-SA 4.0), so **no model trained
on it is released**. This is an owner decision recorded in the selection report.

## 4. Forecasting and anomaly detection

Source: `docs/ml/dataset-research/experiments/time-series-results.json`. The model is chosen on the
development segment only and then scored once on the held-out final segment; error is mean absolute error
relative to the naive baseline.

| Series | Model chosen on development | Test error relative to naive |
|---|---|---|
| Austin reference series (875 weeks) | Holt-Winters | 0.804 |
| Ballarat reference series (767 weeks) | Holt-Winters | 0.731 |
| Boralesgamuwa, Dehiwala (365 weeks each) | naive (nothing beat it on development) | 1.0 by construction: no improvement over the baseline |
| Homagama | excluded: 126 of 362 weeks would be interpolated (above the 25% gate) | n/a |
| Moratuwa | excluded: ticket dates look day/month-swapped for days up to 12 | n/a |
| Kerawalapitiya | per-vehicle tickets; used for anomaly experiments only | n/a |

Interpretation: Holt-Winters beats the naive baseline on two long series (about 20–27% lower error). On the
two shorter, noisier series the development segment favoured the naive model, so no improvement is claimed;
on their test segments some smoothing models were in fact slightly better than naive, which shows how
unstable model selection is on short, noisy series. The 80% prediction interval covered 82.5% (Boralesgamuwa)
and only 59.4% (Dehiwala) of test weeks there, so intervals are not reliable on such data. The API reports the
baseline beside every forecast. No anomaly precision or recall
is reported because there are no labels.

## 5. Route ordering

Source: `docs/ml/dataset-research/experiments/route-validation-ksu.json`. On the public King Saud University
instances the observed route length was 1.096 times the optimum on average for the recorded order, 1.173
for nearest-neighbour, and 1.000 for the project's heuristic on these instances. Distances are straight-line;
no travel-time estimate is made.

## 6. Software quality

| Check | Result |
|---|---|
| Backend tests (real PostgreSQL 16) | 525 passed, 0 skipped (local full run; CI result is recorded in `IMPLEMENTATION_STATUS.md`) |
| Frontend tests | 220 tests in 27 files |
| ML tests | 57 passed |
| End-to-end (Playwright, local) | 21 passed, 1 skipped (local; the skip is the no-model test) |
| Mutation checks | every deliberately broken rule was caught by a test; two incident-module survivors are behaviour-equivalent mutations |
| Dependency audit | `npm audit` 0; `pip-audit` clean for runtime dependencies after the `cryptography` range change |
| Real GitHub CI | everything green except GitGuardian, whose one finding is a reviewed false positive on a test credential |

## 7. Limitations (summary; full list in `docs/project-completion/LIMITATIONS.md`)
Classifier accuracy outside its training domain; frozen backbone; no organic, textile, e-waste or battery
classes (inputs of those kinds go to review); forecasting needs history that a new deployment lacks; straight-line routing; no
no marketplace payment, delivery or photos, no sensor integration, no map geometry; rewards have no redemption; MFA is optional and TOTP only.
