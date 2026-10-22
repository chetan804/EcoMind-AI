# Waste classification

**Status:** `2.0.0` (RealWaste only) is a **research candidate: NOT approved, inactive, not releasable.** It passes five of six
offline acceptance criteria and **fails the sixth** (out-of-scope images sent to review: 79.7% vs the required 90%); the
Hyderabad field evaluation (`docs/ml/field-evaluation-protocol.md`) has not been done; and the RealWaste licence is
conflicting (UCI: CC BY 4.0; authors' GitHub: CC BY-NC-SA 4.0). `1.0.0`, trained on TrashNet, is **withdrawn**: TrashNet and
TrashBox are prohibited in every dataset (no written permission for the photographs; SHA-256 denylist in
`datasets/manifests/prohibited-sha256.txt`).
Evidence: [model card](../../docs/ml/model-cards/waste-classification-2.0.0.md),
[evaluation report](../../docs/ml/reports/waste-classification-2.0.0.md),
[registry manifest](../model_registry/waste_classification/2.0.0.yaml),
[dataset manifest](../../datasets/manifests/realwaste-2.0.yaml).

## What it does
- **Input:** one image (JPEG/PNG/WebP), decoded and centre-cropped by `ml/common/preprocessing/images.py`.
- **Output:** a *material* category (`cardboard`, `glass`, `metal`, `paper`, `plastic`; each is a
  `material_categories.code` in the backend), a **calibrated** confidence, the full class distribution, and
  `needs_review` with reasons (`low_confidence`, `unfamiliar_image`).
- **Not produced:** `object_label` / `object_confidence`. The training data has no object-level labels, so
  the backend stores `NULL` there. Disposal guidance is not a model output (it comes from the sorting guide).
- **Not recognised:** organic/food waste, vegetation, textiles, "miscellaneous trash" (never treated as a material), e-waste,
  hazardous items. The review gate sent 79.7% of the RealWaste images of these kinds to a person, which is **below** the
  required 90%; route such cases to human review.

## Method (all choices and their evidence are in the report)
Frozen ImageNet-pretrained EfficientNet-EdgeTPU TFLite backbone -> L2-normalised features -> logistic-regression
head -> temperature scaling -> review rule. Fine-tuning a CNN is not feasible on the available hardware
(2 CPU cores, no GPU) and would be riskier with ~3k images; a frozen backbone plus a regularised linear head is
the overfit-resistant choice here. "Confidence" is **calibrated** (mean confidence matches accuracy), not maximised.

## Layout
| Path | Purpose |
|---|---|
| `research/` | **Tombstones** (`WITHDRAWN = True`; `main()` exits): the cross-dataset, multi-dataset and TrashBox experiments depended on TrashNet. Kept so the history is explicit. |
| `data/fetch.py` | Fetch RealWaste (pinned commit), the TrashNet *denylist hashes only*, and the backbones; verify SHA-256 (all git-ignored). |
| `data/provenance.py` | Fail-closed gate: manifest completeness, prohibited-dataset and denylist checks, label-mapping rules, file hashes, content digest, licence status. |
| `data/dataset.py`, `data/imagefolder.py` | Verified loading, near-duplicate grouping, group-aware stratified split, leakage checks. |
| `evaluation/field.py` | Validates a Hyderabad field set (permission, consent, privacy, two-person labels, no training/prohibited overlap) and scores it; binds the report to the model's weight hashes. |
| `training/features.py` | Embedding extraction with cache; hand-crafted baseline features. |
| `training/pipeline.py` | Fit, grouped CV, 1-SE selection, review rule, metrics (pure functions). |
| `training/train.py` | The whole run, in protocol order; writes the artifact, registry manifest and report JSON. |
| `evaluation/robustness.py`, `evaluation/report.py` | Synthetic perturbations; renders figures, report and model card from the JSON. |
| `inference/` | `TFLiteEmbedder`, `WasteClassifier` (the serving path), orientation variants. |
| `experiments/preprocessing_ablation.py` | Crop vs squash vs pad (train split only). Ported to the verified loader; **not re-run for 2.0.0**. |
| `../configs/waste_classification.yaml` | Every tunable value, including seeds. |

## Reproduce
```bash
pip install -r ml/requirements.txt
python -m ml.waste_classification.data.fetch                       # RealWaste (1.3 GB git fetch) + backbones, hashes verified
python -m ml.waste_classification.training.train                   # ~30 min on 2 CPU cores the first time (embeddings are cached)
python -m ml.waste_classification.experiments.preprocessing_ablation   # optional; not re-run for 2.0.0
python -m ml.waste_classification.evaluation.report                # figures, report, model card
```
The run is seeded (42) and meant to be deterministic; an independent re-run has not been compared.
Output goes to `ml/artifacts/waste_classification/<version>/` (git-ignored: `head.npz`,
`novelty_reference.npy`, `model.json`).

## Deploying an artifact to the API
Copy `ml/artifacts/waste_classification/<version>/` and `ml/artifacts/_backbones/` into
`$MODEL_ARTIFACTS_DIR` (same layout), then from `backend/`:
`python -m app.cli register-model --version <version>` and `python -m app.cli activate-model --version <version>`.
Both verify every file's SHA-256 first, and activation is **refused (409 `model_not_approved`)** unless the artifact's
`model.json` carries `release.approved_for_activation: true`, which the pipeline writes only when every acceptance criterion and
the field evaluation pass. Today none does. Until a model is activated the API answers `503 no_active_model`.

## Rules
Never evaluate the test split more than once per run (enforced in `train.py`); never change the selection rule
after seeing results; regenerate the report instead of editing numbers by hand; a model without a card is not activated.
