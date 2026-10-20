# Model card: waste material classifier 1.0.0

**Status: candidate.** Trained and evaluated on one public studio-style dataset. Not validated on field data and not
approved for unattended use. Full evidence: `docs/ml/reports/waste-classification-1.0.0.md`.

## Model details
- **Task:** assign one of six *material* categories (cardboard, glass, metal, paper, plastic, trash) to a photograph of a single waste item, with a calibrated confidence and a `needs_review` flag. It does **not** identify the object (no object label is produced).
- **Architecture:** frozen ImageNet-pretrained EfficientNet-EdgeTPU-M embedding extractor (TFLite, uint8; Apache-2.0, google-coral/test_data @ `104342d2`) -> logistic-regression head (numpy) -> temperature scaling.
- **Runtime:** `ai-edge-litert` + numpy + Pillow on CPU. No GPU, no PyTorch/TensorFlow. Artifact files are verified by SHA-256 before loading.
- **Owner/contact:** project maintainers (repository `chetan804/EcoMind-AI`). **Version/date:** 1.0.0, 2026-10-20T10:07:18Z.

## Intended use
Decision support for triaging citizen waste reports: suggest a material category and tell a reviewer when to look. Reviewer
corrections are stored with the prediction and are the intended source of future training data.

## Out of scope
Final regulatory or billing decisions; hazardous, medical, e-waste, organic/food or textile identification; scenes with several
items or heavy clutter; any unattended sorting; inferring anything about people.

## Training data
TrashNet resized (`datasets/manifests/trashnet-1.0.yaml`): 2,527 photographs, MIT-licensed repository, white-posterboard studio setting, three iPhone models, 2016-17.
Class counts: cardboard 403, glass 501, metal 410, paper 594, plastic 482, trash 137. No personal data intended. Labels are the authors' and were not audited.

## Evaluation (held-out group-aware test split, n = 421, evaluated once)
| | |
|---|---|
| Accuracy | **0.867** (95% CI 0.813-0.912) |
| Macro-F1 | **0.841** (95% CI 0.781-0.887) |
| Calibration (ECE) | 0.031; mean confidence 0.869 vs accuracy 0.867 |
| With the review rule | 74% auto-accepted at 96.1% accuracy; 79% of errors sent to review |
| Best baseline (hand-crafted features) | macro-F1 0.592 |
| Latency (2 CPU cores, bytes to decision) | p50 23 ms, p95 30 ms |

**Review rule:** needs review when calibrated confidence < 0.81 or similarity to the training images < 0.570.

## Known weaknesses
- **Studio-to-field gap, measured on one real-world dataset.** On RealWaste (4,752 photographs from a recycling facility in Wollongong, Australia; never seen in training; CC BY-NC-SA 4.0, evaluation only) this model reaches 0.45 accuracy (95% CI 0.44-0.47) and macro-F1 0.51 on the five mappable material classes, with ECE 0.26 (over-confident). The review rule sends 64% of those images to a person; the auto-accepted 36% are 55% accurate. 96% of food, vegetation and textile images (classes this model does not have) are sent to review. Details: `docs/ml/dataset-research/experiments/cross-dataset-realwaste.json` and `docs/ml/dataset-research/DATASET_SELECTION_REPORT.md`. Treat every field prediction as a suggestion.
- Glass is frequently confused with metal and plastic; `trash` is the weakest class (F1 0.65, 23 test images).
- Worst synthetic stress: **occlusion (~30% area)** (accuracy 0.66; auto-accepted accuracy 0.82), where the model is over-confident.
- Only six classes: items outside them will be forced into one (mitigated, not solved, by the novelty gate; tested only on a ten-input smoke set).
- Generalisation gap: train macro-F1 0.98 vs held-out ~0.84; limited by data diversity, not by tuning.
- Residual near-duplicate similarity across the split (see report section 1), so the test score may be slightly optimistic.
- Collected in one place and time; Indian municipal waste (packaging, materials, regional streams) is not represented.

## Ethical and privacy notes
Training images contain no people by design. Inference inputs are user photographs that may contain people or places; the upload
pipeline strips EXIF/GPS metadata and stores images under the platform's access rules. Predictions must be shown as suggestions with their confidence.

## Recommendations
Collect and label local field images (with consent), route low-confidence cases to reviewers, monitor review/correction rates
for drift, re-estimate the review threshold on field data before relying on it, and retrain from reviewed corrections.

## Provenance
git `12c93a5475d6`; config SHA-256 `5898e145369a0b23...`; dataset digest `73cfe75b6a3e1bf1...`; `model.json` SHA-256 `389d431647131968...`.
Registry entry: `ml/model_registry/waste_classification/1.0.0.yaml`.
