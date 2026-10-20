# Waste classification

**Status:** `1.0.0` trained and evaluated on TrashNet; **candidate**, not validated on field data.
Evidence: [model card](../../docs/ml/model-cards/waste-classification-1.0.0.md),
[evaluation report](../../docs/ml/reports/waste-classification-1.0.0.md),
[registry manifest](../model_registry/waste_classification/1.0.0.yaml).

## What it does
- **Input:** one image (JPEG/PNG/WebP), decoded and centre-cropped by `ml/common/preprocessing/images.py`.
- **Output:** a *material* category (`cardboard`, `glass`, `metal`, `paper`, `plastic`, `trash`; each is a
  `material_categories.code` in the backend), a **calibrated** confidence, the full class distribution, and
  `needs_review` with reasons (`low_confidence`, `unfamiliar_image`).
- **Not produced:** `object_label` / `object_confidence`. The training data has no object-level labels, so
  the backend stores `NULL` there. Disposal guidance is not a model output (it comes from the sorting guide).
- **Not recognised:** organic/food waste, e-waste, textiles, hazardous items. The novelty gate helps, but it is
  only smoke-tested (see the report); route such cases to human review.

## Method (all choices and their evidence are in the report)
Frozen ImageNet-pretrained EfficientNet-EdgeTPU TFLite backbone -> L2-normalised features -> logistic-regression
head -> temperature scaling -> review rule. Fine-tuning a CNN is not feasible on the available hardware
(2 CPU cores, no GPU) and would be riskier with ~2.5k images; a frozen backbone plus a regularised linear head is
the overfit-resistant choice here. "Confidence" is **calibrated** (mean confidence matches accuracy), not maximised.

## Layout
| Path | Purpose |
|---|---|
| `data/fetch.py` | Fetch TrashNet and the backbones at pinned commits; verify SHA-256 (all git-ignored). |
| `data/trashnet.py` | Loader, near-duplicate grouping, group-aware stratified split. |
| `training/features.py` | Embedding extraction with cache; hand-crafted baseline features. |
| `training/pipeline.py` | Fit, grouped CV, 1-SE selection, review rule, metrics (pure functions). |
| `training/train.py` | The whole run, in protocol order; writes the artifact, registry manifest and report JSON. |
| `evaluation/robustness.py`, `evaluation/report.py` | Synthetic perturbations; renders figures, report and model card from the JSON. |
| `inference/` | `TFLiteEmbedder`, `WasteClassifier` (the serving path), orientation variants. |
| `experiments/preprocessing_ablation.py` | Crop vs squash vs pad (train split only). |
| `../configs/waste_classification.yaml` | Every tunable value, including seeds. |

## Reproduce
```bash
pip install -r ml/requirements.txt
python -m ml.waste_classification.data.fetch                       # data + backbones, hashes verified
python -m ml.waste_classification.training.train                   # ~10 min on 2 CPU cores
python -m ml.waste_classification.experiments.preprocessing_ablation   # optional, ~3 min
python -m ml.waste_classification.evaluation.report                # figures, report, model card
```
The run is deterministic (same seed, same data): two runs gave identical test metrics.
Output goes to `ml/artifacts/waste_classification/<version>/` (git-ignored: `head.npz`,
`novelty_reference.npy`, `model.json`).

## Deploying an artifact to the API
Copy `ml/artifacts/waste_classification/<version>/` and `ml/artifacts/_backbones/` into
`$MODEL_ARTIFACTS_DIR` (same layout), then from `backend/`:
`python -m app.cli register-model --version 1.0.0` and `python -m app.cli activate-model --version 1.0.0`.
Both verify every file's SHA-256 first. Until a model is activated the API answers `503 no_active_model`.

## Rules
Never evaluate the test split more than once per run (enforced in `train.py`); never change the selection rule
after seeing results; regenerate the report instead of editing numbers by hand; a model without a card is not activated.
