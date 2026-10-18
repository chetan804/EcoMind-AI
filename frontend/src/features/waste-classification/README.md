# Feature: waste-classification

AI waste classification screen at `/classify`: image upload, result panel, planned class grid.

**Status:** UI implemented (Stage 1 UI milestone). **No classification exists.** No model has been trained, there is no classification endpoint, and the page never produces a prediction.

- **Backend module (future):** `classification` (with `sorting_guide` for categories); training and inference live in `ml/waste_classification/`.
- **What works:** choosing or dropping a JPEG, PNG or WebP file up to 5 MB (`schemas/image-file.ts`) validates it and shows a **local preview**. Nothing is uploaded. The result panel then says classification is not available yet.
- **Layout preview:** a switch under the result card shows labelled sample content ("Sample layout", "not a model result") so the design can be reviewed. It has no confidence number or accuracy; "Model: Not connected", "Evaluation: Not evaluated". `fixtures/` is only used by this preview.
- **Unavailable controls:** "Verify result" uses `unavailableReason`.
- **Class grid:** titled "Planned waste classes"; it lists the label set in scope, not supported classes.
- **When the backend exists:** add `api/` and a mutation hook, show the real result and its evaluated metrics from the API, and keep the unavailable state for failures. Do not show model accuracy that is not backed by `docs/ml/model-cards/`.
- **Public interface:** `import { ClassificationPage } from '@/features/waste-classification'`.
