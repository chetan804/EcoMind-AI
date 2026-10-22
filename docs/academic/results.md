# Results

All figures are copied from committed artifacts; the artifact is named in each row. Counts of tests are from
local runs on 2026-10-22 unless stated; CI results are in `docs/project-completion/REQUIREMENTS_CLOSURE_REPORT.md`
and `IMPLEMENTATION_STATUS.md`. The classifier was trained on 2026-10-22 (one run; no independent re-run yet).

## 1. Classifier `waste-classification 2.0.0` (research candidate: NOT approved, inactive)

Source: `docs/ml/reports/waste-classification-2.0.0.{json,md}`, model card
`docs/ml/model-cards/waste-classification-2.0.0.md`, field protocol `docs/ml/field-evaluation-protocol.md`.
The earlier model `1.0.0` (trained on TrashNet) was **withdrawn on 2026-10-22** because the project has no written
permission for TrashNet's photographs. **None of its figures appears here.** The new model was trained once, on
2026-10-22, from RealWaste alone (pinned commit `156e8e91`, 4,752 images); TrashNet and TrashBox are excluded by a
SHA-256 denylist that is checked on every load.

**Data.** Five classes with a justified mapping (cardboard, glass, metal, paper, plastic: 3,092 images). The folders
"Miscellaneous Trash", "Food Organics", "Vegetation" and "Textile Trash" (1,660 images) are **not** treated as materials,
are never trained on, and are used only to test review routing. Near-duplicate photographs are clustered (1,390 groups,
largest 72 images) and a stratified group split was fixed before modelling (seed 42): train 2,060, validation 516, test 516.

| Measure (RealWaste held-out test split, n = 516, evaluated once) | Value |
|---|---|
| Accuracy | 0.895 (95% CI 0.855 to 0.931, group bootstrap) |
| Macro-F1 | 0.896 (95% CI 0.851 to 0.929) |
| Expected calibration error | 0.036 (temperature 0.750 fitted on validation) |
| Top-2 accuracy | 0.984 |
| Auto-accepted share / accuracy of those | 82.9% / 93.5% (Wilson 95% CI 90.7% to 95.4%); 48% of the errors go to review |
| Weakest class | plastic (F1 0.865, recall 0.851) |
| Most frequent confusions | plastic predicted as glass (11 images); metal predicted as plastic (10) |
| Majority-class / hand-crafted-feature baselines, macro-F1 | 0.092 / 0.636 (the model beats the better one by 0.260) |
| CPU latency, median / p95 (shared 2-core sandbox) | 76 ms / 86 ms |

Per class on the test split (precision / recall / F1): cardboard 0.859 / 0.948 / 0.901; glass 0.840 / 0.900 / 0.869;
metal 0.952 / 0.909 / 0.930; paper 0.926 / 0.904 / 0.915; plastic 0.879 / 0.851 / 0.865. The full confusion matrix,
reliability diagram, selective-accuracy curve, regularisation sweep and learning curve are in the report and
`docs/ml/reports/figures/`.

Model selection used grouped 5-fold cross-validation on the training split only (selected: M+L backbones, C = 0.03,
no test-time augmentation; CV macro-F1 0.854); validation macro-F1 was 0.878 and in-sample training macro-F1 0.976, so
the train-to-CV gap is 0.124: the linear head fits its training images much better than held-out ones.

**Leakage, measured.** The same recipe under a naive random split scores accuracy 0.905 and macro-F1 0.904, and 31.8%
of its test images have a same-class near-twin in training; under the group split the figure is 5.8%. Grouping reduces
but does not remove similarity, so the 0.895 may still be slightly optimistic.

**Robustness (synthetic proxies on the test images).** accuracy under dark 0.843, bright 0.810, low contrast 0.822, blur
0.835, JPEG quality 15 0.843, sensor noise 0.828, low resolution (48 px) 0.760, rotation 20 degrees 0.729 and
**30% occlusion 0.624**. The background perturbations barely change RealWaste photographs and are not evidence of
robustness to clutter.

## 2. Pre-declared acceptance test (set in `ml/configs/waste_classification.yaml` before the run)

| Criterion | Required | Observed | Result |
|---|---|---|---|
| Test macro-F1 | at least 0.80 | 0.896 | pass |
| Minimum per-class recall | at least 0.60 | 0.851 | pass |
| Expected calibration error | at most 0.08 | 0.036 | pass |
| Margin over hand-crafted baseline (macro-F1) | at least 0.10 | 0.260 | pass |
| Accuracy of auto-accepted predictions, 95% CI lower bound | at least 0.90 | 0.907 | pass |
| **Out-of-scope images sent to review** | **at least 0.90** | **0.797** | **FAIL** |
| Hyderabad field evaluation | at least 300 images, macro-F1 at least 0.75, auto-accepted accuracy at least 0.90 | **not done** | **not met** |

**Decision: NOT APPROVED.** The criteria were not changed after the results were seen. Out-of-scope routing, by source
folder: Food Organics 83.9%, Textile 72.3%, Miscellaneous 68.3%, Vegetation 94.0% (1,660 images, 79.7% overall); without
the review rule these images would have been called cardboard, metal, plastic or paper. Of ten non-waste smoke-test inputs
(ImageNet-style photographs and synthetic images), 10 were routed to review; that is a smoke test, not a measurement.

## 3. What the numbers do not say
* RealWaste is **one facility in Wollongong, Australia**. The scores are **not** a Hyderabad accuracy, and no field image
  has been collected (the protocol is written; there are no field results).
* The RealWaste licence is **conflicting** (UCI: CC BY 4.0; authors' GitHub: CC BY-NC-SA 4.0), so the model is research-only
  and cannot be released until the authors confirm the licence for the exact files in writing.
* 77% of the images share a group with another photograph; the test split is cleaner than a naive one but not independent.
* One seed, one split, one dataset. The preprocessing ablation that was run for `1.0.0` was not repeated for `2.0.0`.
* A cross-dataset result (training on one dataset, testing on another) is no longer available, because the only other
  dataset, TrashNet, is prohibited. The earlier cross-dataset, multi-dataset and TrashBox experiments are withdrawn.

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
and only 59.4% (Dehiwala) of test weeks there, so intervals are not reliable on such data. On the two long series the 80% interval covered 84.9% (Austin) and 81.0% (Ballarat) of test weeks. On the unmodified series the anomaly
scorer raised 2.1 to 5.7 alerts per 100 weeks (Austin 2.1, Ballarat 2.6, Boralesgamuwa 4.2, Dehiwala 5.7), (some of which may be genuine events, since there are no labels, so this is an
alert rate, not a false-positive rate). The API reports the
baseline beside every forecast. No anomaly precision or recall
is reported because there are no labels.

## 5. Route ordering

Source: `docs/ml/dataset-research/experiments/route-validation-ksu.json` (public Kalasin University campus
waste-collection routes, Thailand; repository `kamthornsa/ksu-waste-collection-dataset`, CC BY 4.0 as recorded when the
validation was built; five observed days with 8 to 21 stops). Every route is measured in **road metres**:

| Route | Mean length ÷ exact optimum |
|---|---|
| Route actually driven | 1.096 (range 1.004 to 1.217) |
| Nearest neighbour | 1.173 |
| Project heuristic when given the road-distance matrix | 1.000 (matched the exact optimum on all 5 days) |
| Project plan built from straight-line distances only (what the shipped API does) | 1.028 (range 1.000 to 1.079) |

So the shipped planner, which has no road network, costs about 3% extra road distance on this campus compared with
planning on real road distances. Five days on one small campus are indicative only and say nothing about city-scale
networks, traffic or time windows. The platform estimates no travel time.

## 6. Software quality

Local runs on one machine (2 CPUs, PostgreSQL 16.2, headless Chromium; the end-to-end, audit and backup rows are from 2026-10-21); CI results are separate.

| Check | Result |
|---|---|
| Backend tests (real PostgreSQL 16, CI-like environment) | 786 passed, 1 skipped (a clean checkout lacks the git-ignored model file that the classification parity test needs; with it, 787 passed and 0 skipped, run 2026-10-21); 8 min 13 s, run on 2026-10-22 |
| Frontend tests (Vitest) | 386 passed in 39 files |
| ML tests | 118 passed |
| Contract and structure tests | 147 passed |
| End-to-end (Playwright, local, 63 tests) | 61 passed, 2 skipped: the real-model test (no model is active) and the forced two-step enrolment test (needs a stack that enforces it in production mode; it was run separately on such a stack: 4 of 4 in that spec). Mail was read through a local stand-in for Mailpit; CI uses the real Mailpit container |
| Mutation checks | recorded per module in `docs/project-completion/IMPLEMENTATION_STATUS.md` (for example 12 of 12 for authentication, 9 of 9 for administration and audit); not re-run on 2026-10-22 |
| Dependency audit and static analysis | `pip-audit` (backend and ML), `npm audit` (frontend and e2e) and `bandit`: no findings (run on 2026-10-21) |
| Secret scan | `detect-secrets` over tracked files: 127 candidates, all placeholders, throw-away test values, alphabets or content hashes |
| Backup and restore drill | dump and restore at migration 0017: row counts, version and triggers identical (`docs/operations/backup-and-rollback.md`) |
| Real GitHub CI on `main` (`625241e`, 2026-10-21) | all workflows (backend, frontend, quality gates, security, CodeQL) reported success per `REQUIREMENTS_CLOSURE_REPORT.md`; GitGuardian's one finding is a reviewed false positive on a test credential. CI was not re-queried on 2026-10-22 |
| Load (sandbox only: 1 API worker, shared machine, tiny data) | 10 users 130 requests/s, 0% errors, p95 123 ms; 50 users 122 requests/s, p95 639 ms. Not a capacity claim |

## 7. Limitations (summary; full list in `docs/project-completion/LIMITATIONS.md`)
No approved classifier (so none is active), no field evaluation, a contested training-data licence and one failed acceptance criterion; frozen backbone; five
material classes only (organic, textile, e-waste and battery inputs go to review) and no object identification;
forecasting needs history that a new deployment lacks and beat the naive baseline on 2 of 4 usable public series;
anomaly detection has no labelled data (tested on injected spikes only); straight-line route ordering, with optional
road routing verified only against mocked services; offline maps verified only with synthetic tiles; vehicle tracking
verified only with a simulator and emulated geolocation (no real device); e-mail verified only with a local catcher
and a stand-in (no real SMTP provider); marketplace and rewards are hand-over workflows with no payment or delivery;
two-step verification is TOTP only; accessibility is checked by automated tools only (no human keyboard or
screen-reader review); the system has never been deployed or load-tested on target hardware; no user study has been
run.
