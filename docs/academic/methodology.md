# Methodology

## 1. Architecture
A modular monolith (decision record: `docs/decisions/ADR-0001-modular-monolith.md`). React 19 and
TypeScript single-page app (Vite); FastAPI under `/api/v1` with 22 modules and 168 operations; PostgreSQL 16 with
SQLAlchemy 2 and Alembic (46 application tables, 17 migrations, head `0017`); an isolated `ml/` package for
training, evaluation and inference code, kept out of request handlers. Each module owns its tables and talks to
others through services. Diagrams and tables: `docs/architecture/`, `docs/database/er-diagram.md`,
`docs/database/data-dictionary.md`, `docs/database/schema-overview.md`. No message broker, cache server or PostGIS
is used because no verified requirement needs one; the only optional extra service is a self-hosted OSRM routing
engine (ADR-0002), off by default. Deployment is Docker Compose behind nginx; it has been validated by CI but never
run on a real server.

## 2. Security and data-integrity design
Argon2id passwords; 15-minute bearer access tokens held in memory; rotating HttpOnly refresh cookie with
reuse detection and a CSRF header; per-email and per-address lockout derived from the append-only audit log;
deny-by-default RBAC (5 roles, 48 permissions) with permissions re-read from the database on every request; TOTP
two-step verification (RFC 6238) with recovery codes, mandatory for administrators and managers when
`ENVIRONMENT=production`; single-use e-mail tokens for password reset and address verification (never consumed on
page load); validated, re-encoded image uploads with metadata removed; request IDs and a uniform error envelope.
The audit log, chain-of-custody events, the reward ledger, vehicle location events and collection status history are
**append-only at database level** (triggers added in migration 0017 reject UPDATE and DELETE; TRUNCATE is not
covered). Custody events are additionally hash-chained and can be re-verified. Controls and review:
`docs/security/`. Every route's required permission is listed in `docs/security/route-permission-matrix.md` and
guarded by a test. This is a self-review, not an independent penetration test.

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
  bit-for-bit (`docs/ml/dataset-research/ingestion/reproducibility-1.0.0.md`; re-run again on 2026-10-21 with identical accuracy, macro-F1, calibration error and weight hashes). The classifier verifies
  file hashes at load and refuses a tampered artifact.
- **Cross-dataset and multi-dataset study.** The released model is scored on RealWaste's six shared
  classes; separate experiments train on TrashNet, RealWaste, and both, with and without class balancing,
  and report each model on both datasets' held-out splits (`docs/ml/dataset-research/DATASET_SELECTION_REPORT.md`).

## 4. Forecasting and anomaly detection
Weekly series (platform-collected weight, plus two public reference series) with chronological splits.
Candidate algorithms are scored against naive baselines by mean absolute error on a held-out final segment
(`docs/ml/dataset-research/experiments/time-series-results.json`); the forecaster refuses to answer with
fewer than 26 weeks of history (`422 insufficient_history`); the prediction interval is 80%. The forecaster beat the naive baseline on 2 of 4 usable series (relative error 0.804 on the Austin series and 0.731 on Ballarat). Anomalies use a robust z-score against a median baseline (the same week in previous years when enough
history exists, otherwise the previous three weeks), with documented thresholds (3.5 warning, 5 critical); the data carry no incident labels, so **no precision or recall is
claimed**, and alerts are called "suspected anomalies".

## 5. Route ordering
Exact Held-Karp for up to 12 stops; above that, nearest-neighbour followed by 2-opt and Or-opt, seeded
for determinism; at most 40 tasks per plan; straight-line (haversine) distance, no travel-time estimate.
Validated on public Kalasin University (Thailand) waste-collection routes (CC BY 4.0 as recorded), measured in road
metres: the straight-line plan was 1.028 times the road-distance optimum on average over five days. Road routing is optional: a provider
adapter (`ROUTING_PROVIDER=none|google|osrm`) can return a road route on request, nothing is stored, and a
straight-line route is always labelled as a fallback. Only mocked provider responses were tested.

## 6. Maps and vehicle tracking
Maps use MapLibre GL with an optional self-hosted PMTiles file, so no API key is needed; a Google Maps adapter is
optional and key-gated (the key is a server-side setting and never reaches the browser bundle). Vehicle positions
are stored as append-only events with a source (GPS device, mobile client, import or simulator). The interface shows the age
of the last position and labels a stale position STALE; a stored depot coordinate is never drawn as a live
vehicle. Simulator events use a separate permission and source, are labelled "demonstration only" and are removable
without touching real history. No zone boundaries or heat maps are drawn because no verified boundary data exists.

## 7. Help assistant
A retrieval-only assistant (ADR-0003): it matches a question against a curated set of help articles with PostgreSQL
full-text search and reads the asking user's own points, reports and requests; it generates no text and calls no
external language model. If nothing matches it says so and offers a support request. Quality was measured on two
question sets (held-out top-1 0.55; the other set is contaminated by design and says so in
`docs/ml/support-assistant.md`).

## 8. Impact and rewards
Points = round(weight in kg × 10) for a task that came from a verified citizen report, once per user and
task, written to an append-only ledger. The platform ships no rewards: staff enter catalogue items, a citizen redeems with an idempotent request that writes a
negative ledger entry (a cancellation writes a reversing entry), and staff hand the item over (pending to fulfilled or
cancelled). No emission or energy coefficient is used because none has been
sourced; the system shows recovered weight, which is measured.

## 9. Quality assurance
Backend tests against real PostgreSQL (including migration round trips, schema-constraint tests and drift checks
with `alembic check`), frontend unit and integration tests, ML tests, contract tests for the scripts, a Playwright
end-to-end suite (including keyboard-only tests, forced two-step enrolment and e-mail links read from a mail
catcher), axe accessibility scans over 22 routes in two themes, and **mutation checks** (a rule was deliberately
broken in a module to confirm a test fails). Static checks: ruff, mypy (strict for ML), ESLint, TypeScript, bandit,
`pip-audit`, `npm audit`, detect-secrets and CodeQL. CI runs these on every push (`.github/workflows/`). Generated
documents (data dictionary, ER diagram, route matrix) have `--check` modes that CI runs, so they cannot silently go
stale. Human review is **not** part of the evidence: accessibility, design fidelity and usability have not been
assessed by people.
