# Waste classification (`classification`)

Serves the trained material classifier from `ml/waste_classification`, stores every prediction against the
model version that produced it, and records human review. The model's own output is never rewritten: a review
adds fields beside it.

**Status:** implemented (API, service, repository, runtime, CLI, migration `0004`). It serves whatever artifact
is *activated*; with none active it answers `503 no_active_model` and fabricates nothing.

## Ownership
- **Tables owned:** `classification_model_versions`, `classification_predictions` (columns for review reasons,
  class probabilities, novelty similarity and latency were added by migration `0004`, which also seeds the six
  `material_categories` the model predicts).
- **Files:** `router.py` (HTTP), `service.py` (rules, audit, idempotency), `repository.py` (queries),
  `schemas.py`, `errors.py`, `models.py`, `runtime.py` (numpy + TFLite inference, no ML training code),
  `provider.py` (artifact verification and a process-level runtime cache).
- **Depends on:** `waste_reports` (`MediaAsset` is the image source), `auth` (principal, permissions),
  `audit`. The backend image has no `ml/` directory, so `runtime.py` re-implements the small serving path;
  `tests/integration/test_classification_parity.py` proves it matches the `ml/` classifier (it is skipped
  where the git-ignored artifact is absent).

## API (`/api/v1/classification`; details in `docs/api/classification-api.md`)
| Method and path | Permission | Notes |
|---|---|---|
| `GET /model` | any signed-in user | Active model summary, or `active: null`. |
| `GET /models`, `POST /models/{id}/activate` | `classification:manage_models` | Activation re-verifies every file hash. |
| `POST /predictions` | `classification:predict` | Body `{media_id}`; owner (or `read_all`) only; idempotent per image and model. |
| `GET /predictions`, `GET /predictions/{id}` | reviewers / owner | Filters: `needs_review`, `review_status`, `model_version_id`. |
| `POST /predictions/{id}/review` | `classification:review` | `confirmed`, `corrected` (needs a different known category), `rejected`; once only. |

## Model lifecycle (CLI, from `backend/`)
`python -m app.cli register-model --version 1.0.0` then `python -m app.cli activate-model --version 1.0.0`.
Artifacts live in `$MODEL_ARTIFACTS_DIR/waste_classification/<version>/` plus `_backbones/`. The registered
SHA-256 of `model.json` binds the row to exact bytes; a modified artifact is refused at registration,
activation and load. Only one version can be active (partial unique index).

## Safety properties
Calibrated confidence plus a `needs_review` flag (`low_confidence`, `unfamiliar_image`); no prediction is
stored when inference fails; undecodable or oversized images are `422`; all other users' images are `404`.

## Tests
`tests/api/test_classification.py` (HTTP, RBAC, idempotency, review, activation, tamper), `tests/unit/test_classification_runtime.py`,
`tests/integration/test_classification_schema.py` (migration seed, round trip), `test_cli.py` (model commands),
`test_classification_parity.py` (real artifact; skipped when absent). Run: `make test-backend`.
