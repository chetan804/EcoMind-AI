# Feature: waste-classification

AI waste classification screen at `/classify`: choose an image, classify it with the model the server has activated, see the result, and (for reviewers) confirm, correct or reject it.

**Status:** working against the real API (`docs/api/classification-api.md`). Verified by vitest (11 page tests), 4 UI mutation checks and a Playwright journey against the real backend with the trained model (`tests/e2e/specs/classification.spec.ts`), which is **skipped** when no model is active (CI and a fresh install have none, so that journey is not exercised there).

## Flow
1. On load, `GET /classification/model` says whether a model is active. If none is, the page says so, still previews a chosen image, and offers no Classify button. Nothing is uploaded.
2. Choosing a JPEG, PNG or WebP up to 5 MB validates and previews it locally (`schemas/image-file.ts`).
3. **Classify image** uploads the file (raw body via `apiRequest`, to `/waste-reports/media`) and then calls `POST /classification/predictions`. The button is unavailable, with a reason, for roles without `classification:predict` and `waste_reports:create`.
4. The result shows the category, **calibrated** confidence, all six probabilities, a "Needs review" badge with reasons, the model name/version, the model's recorded held-out accuracy ("studio photos, not a field accuracy") and the review state.
5. Roles with `classification:review` get a review form (confirm / correct with a different category / reject). The server allows one review per prediction and never rewrites the model output.

## Review queue (`/classify/review`)
For `classification:review` (administrators, managers, facility operators). Lists the model's suggestions through `GET /classification/predictions` (default: `needs_review=true` and `review_status=unreviewed`; the selector also shows confirmed, corrected and rejected outcomes), shows the photo through `GET /classification/predictions/{id}/image` (a reviewer needs no report-reading right), and reuses `ReviewPanel`. Finished reviews show their outcome and no form. Covered by `tests/integration/review-queue.test.tsx`.

## States
Model loading, model status error (retry), no active model, empty, ready, analysing, error (specific text for `no_active_model`, `model_unavailable`, `invalid_image`, too large, rate limited; retry), result, reviewed. No state shows a prediction that the server did not return.

## Structure
`api/` (zod-validated calls), `hooks/` (TanStack Query), `components/`, `utils.ts` (error and reason wording), `schemas/image-file.ts`. The category grid is a constant that mirrors `docs/ml/model-cards/waste-classification-1.0.0.md`; it says the model does not cover organic waste, e-waste or hazardous items.

## Limits
Classifying stores the uploaded image (no purge of unattached media yet). The correction list uses the model's class codes, which equal the `material_categories` codes today. Public interface: `import { ClassificationPage } from '@/features/waste-classification'`.
