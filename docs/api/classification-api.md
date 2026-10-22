# Classification API

Base path `/api/v1/classification`. Conventions (envelope, pagination, request IDs) are in
`api-conventions.md`; authentication in `auth-api.md`. The model scope is **material category only**
(`cardboard`, `glass`, `metal`, `paper`, `plastic`, `trash`); `object_label` is always `null`.
Model evidence: `docs/ml/model-cards/waste-classification-1.0.0.md`.

## Flow
1. `POST /api/v1/waste-reports/media` (raw image body) returns `media_id`.
2. `POST /classification/predictions {"media_id": "..."}` returns the prediction.
3. Optionally attach `media_id` to a waste report; a reviewer confirms or corrects the prediction later.

## Endpoints
| Method, path | Permission | Success | Notes |
|---|---|---|---|
| `GET /model` | signed in | 200 | `{active, scope, note}`; `active` is `null` when no model is active. |
| `GET /models` | `classification:manage_models` | 200 | All registered versions. |
| `POST /models/{id}/activate` | `classification:manage_models` | 200 | Re-verifies every artifact hash and requires the artifact's own release record (`model.json` → `release.approved_for_activation == true`, written by the training pipeline only when the acceptance criteria and the field evaluation pass); otherwise **409 `model_not_approved`** (fail closed: a missing record counts as not approved). The previous active version becomes `retired`. Re-activating the active version is a no-op. |
| `POST /predictions` | `classification:predict` | 201 / 200 | Body `{media_id}` (unknown fields rejected). 200 + `Idempotent-Replayed: true` when the image was already classified by the active model. |
| `GET /predictions` | `classification:review` | 200 | Paginated; filters `needs_review`, `review_status`, `model_version_id`. |
| `GET /predictions/{id}/image` | `classification:review` | 200 | The classified photo (image bytes, `nosniff`, sandbox CSP), so a reviewer can judge the suggestion; reviewers need no report-reading right. `404` for an unknown prediction. |
| `GET /predictions/{id}` | `classification:predict` | 200 | Owner of the image, or a user with `waste_reports:read_all`; otherwise 404 (existence is not revealed). |
| `POST /predictions/{id}/review` | `classification:review` | 200 | Body `{decision: confirmed|corrected|rejected, material_category_code?, notes?}`. |

## Prediction object
`id`, `media_asset_id`, `model_name`, `model_version`, `material_category {id, code, name}`,
`confidence` (calibrated probability of that category, 0 to 1), `class_probabilities` (one per class the model has, sum to 1),
`needs_review` and `review_reasons` (`low_confidence`, `unfamiliar_image`), `novelty_similarity`,
`inference_ms`, `object_label` (null), `review {status, corrected_category, reviewed_by_id, reviewed_at, notes}`,
`created_at`.

**Reading confidence.** It is calibrated on held-out photographs *from the model's own training dataset* (see the model card for the
measured calibration error): it is *not* a guarantee in the field, where it is unmeasured. When `needs_review` is true, show the label as a suggestion and
route the image to a person.

## Errors (envelope `{error: {code, message, request_id}}`)
| Status | `code` | When |
|---|---|---|
| 401 / 403 | `unauthenticated` / `forbidden` | Missing or insufficient credentials. |
| 404 | `not_found` | Image or prediction not visible to the caller. |
| 404 | `model_version_not_found` | Unknown model id. |
| 409 | `prediction_already_reviewed` | A prediction can be reviewed once. |
| 409 | `model_not_approved` | Activation refused: the artifact is not marked `approved_for_activation`. |
| 422 | `invalid_image` | Not a decodable JPEG/PNG/WebP, or too many pixels. |
| 422 | `invalid_review` | `corrected` without a known category, or the same category as predicted. |
| 503 | `no_active_model` | No model is active. Nothing is stored or faked. |
| 503 | `model_unavailable` | Artifact missing, modified, or its category is not configured. Nothing is stored. |

## Audit
`classification.predicted`, `classification.reviewed`, `classification.model_registered`, `classification.model_activated`.
