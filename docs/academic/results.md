# Results

All figures are copied from committed artifacts; the artifact is named in each row. Counts of tests are from
local runs on 2026-10-22 unless stated; CI results are in `docs/project-completion/REQUIREMENTS_CLOSURE_REPORT.md`
and `IMPLEMENTATION_STATUS.md`. The classifier was re-trained from scratch on 2026-10-21 and reproduced the
accuracy, macro-F1, calibration error and weight hashes below.

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

Further rows from the same report (`docs/ml/reports/waste-classification-1.0.0.json`):

| Check | Value |
|---|---|
| Majority-class baseline, test accuracy / macro-F1 | 0.235 / 0.063 |
| Hand-crafted-feature logistic regression, test accuracy / macro-F1 | 0.618 / 0.592 (the model beats it by 0.249 macro-F1) |
| Naive random split instead of the group-aware split (leakage study) | accuracy 0.893 vs 0.867: near-duplicate photos inflate the estimate by about 2.7 points, which is why the group split is used |
| In-sample training accuracy | 0.980 (a gap to 0.867 that shows over-fitting capacity; the head is regularised and selected by cross-validation) |
| Robustness of test accuracy under perturbation | dark 0.860; bright 0.834; blur 0.822; JPEG quality 15 0.824; sensor noise 0.803; low contrast 0.781; rotation 20° 0.834; low resolution (48 px) 0.746; **30% occlusion 0.660** |
| Latency (2 CPU cores, no GPU, single request, includes decoding) | median 23.1 ms, p95 29.6 ms |

## 2. Cross-dataset generalisation (RealWaste, real facility photographs)

Source: `docs/ml/dataset-research/experiments/cross-dataset-realwaste.json`.

| Measure (in-scope shared classes, n = 3,092) | Value |
|---|---|
| Accuracy | **0.454** (95% CI 0.437 to 0.472) |
| Macro-F1 | 0.514 |
| Expected calibration error | 0.263 |
| Coverage / accuracy of accepted predictions | 36.4% / 55.3% |
| Out-of-scope images (food, textile, vegetation; n = 1,165) sent to review | 95.5% |

Per class on RealWaste (in-scope, n = 3,092): recall is low for cardboard (0.24, 91 of 461 predicted as paper),
glass (0.43), plastic (0.49; confused with metal and glass) and paper (0.46); metal is best (F1 0.63). When RealWaste's
"miscellaneous trash" is mapped to the model's `trash` class (n = 3,587), accuracy is 0.463 and `trash` F1 is only
0.29, so the mapping is approximate and that variant is not used as the headline. Out-of-scope images that were sent
to review: food organics 97.6%, textile 87.1%, vegetation 99.8%.

An independent study reports the same kind of drop for a different model: 94.18% on TrashNet but 41.04% zero-shot on
the overlapping RealWaste classes (Echchidmi and Bouayad 2026, `literature-survey.md` entry 9). The two evaluations
differ in model, split and classes, so only the direction and size of the gap are comparable.

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
| ML tests | 61 passed |
| Contract and structure tests | 147 passed |
| End-to-end (Playwright, local, 63 tests) | 61 passed, 2 skipped: the real-model test (no model is active) and the forced two-step enrolment test (needs a stack that enforces it in production mode; it was run separately on such a stack: 4 of 4 in that spec). Mail was read through a local stand-in for Mailpit; CI uses the real Mailpit container |
| Mutation checks | recorded per module in `docs/project-completion/IMPLEMENTATION_STATUS.md` (for example 12 of 12 for authentication, 9 of 9 for administration and audit); not re-run on 2026-10-22 |
| Dependency audit and static analysis | `pip-audit` (backend and ML), `npm audit` (frontend and e2e) and `bandit`: no findings (run on 2026-10-21) |
| Secret scan | `detect-secrets` over tracked files: 127 candidates, all placeholders, throw-away test values, alphabets or content hashes |
| Backup and restore drill | dump and restore at migration 0017: row counts, version and triggers identical (`docs/operations/backup-and-rollback.md`) |
| Real GitHub CI on `main` (`625241e`, 2026-10-21) | all workflows (backend, frontend, quality gates, security, CodeQL) reported success per `REQUIREMENTS_CLOSURE_REPORT.md`; GitGuardian's one finding is a reviewed false positive on a test credential. CI was not re-queried on 2026-10-22 |
| Load (sandbox only: 1 API worker, shared machine, tiny data) | 10 users 130 requests/s, 0% errors, p95 123 ms; 50 users 122 requests/s, p95 639 ms. Not a capacity claim |

## 7. Limitations (summary; full list in `docs/project-completion/LIMITATIONS.md`)
Classifier accuracy outside its training domain (and no approved model, so none is active); frozen backbone; six
material classes only (organic, textile, e-waste and battery inputs go to review) and no object identification;
forecasting needs history that a new deployment lacks and beat the naive baseline on 2 of 4 usable public series;
anomaly detection has no labelled data (tested on injected spikes only); straight-line route ordering, with optional
road routing verified only against mocked services; offline maps verified only with synthetic tiles; vehicle tracking
verified only with a simulator and emulated geolocation (no real device); e-mail verified only with a local catcher
and a stand-in (no real SMTP provider); marketplace and rewards are hand-over workflows with no payment or delivery;
two-step verification is TOTP only; accessibility is checked by automated tools only (no human keyboard or
screen-reader review); the system has never been deployed or load-tested on target hardware; no user study has been
run.
