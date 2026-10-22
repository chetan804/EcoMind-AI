# Model card: waste material classifier 2.0.0

**Status: RESEARCH CANDIDATE. NOT APPROVED. NOT FOR RELEASE.** Trained only on realwaste 2.0 (licence status: **conflicting**; declared CC-BY-4.0, CC-BY-NC-SA-4.0), so the model may be used for non-commercial research only and must not be distributed, shipped or activated until the dataset licence is confirmed in writing. No field evaluation exists. Acceptance decision: **NOT APPROVED: offline criteria failed and no field evaluation exists**. TrashNet and TrashBox are excluded from every split. Full evidence: `docs/ml/reports/waste-classification-2.0.0.md`.

## Model details
- **Task:** assign one of 5 *material* categories (cardboard, glass, metal, paper, plastic) to a photograph of a single waste item, with a calibrated confidence and a `needs_review` flag. It does **not** identify the object (no object label is produced).
- **Architecture:** frozen ImageNet-pretrained EfficientNet-EdgeTPU-M+L embedding extractor (TFLite, uint8; Apache-2.0, google-coral/test_data @ `104342d2`) -> logistic-regression head (numpy) -> temperature scaling.
- **Runtime:** `ai-edge-litert` + numpy + Pillow on CPU. No GPU, no PyTorch/TensorFlow. Artifact files are verified by SHA-256 before loading.
- **Owner/contact:** project maintainers (repository `chetan804/EcoMind-AI`). **Version/date:** 2.0.0, 2026-10-22T09:07:57Z.

## Intended use
Decision support for triaging citizen waste reports: suggest a material category and tell a reviewer when to look. Reviewer
corrections are stored with the prediction and are the intended source of future training data.

## Out of scope
Final regulatory or billing decisions; hazardous, medical, e-waste, organic/food or textile identification; scenes with several
items or heavy clutter; any unattended sorting; inferring anything about people.

## Training data
realwaste 2.0 (`datasets/manifests/realwaste-2.0.yaml`; UCI dataset 908 / authors' GitHub, pinned commit `156e8e91`): photographs of waste received at one facility in Wollongong NSW, Australia. 3092 images in the five trained classes (cardboard 461, glass 420, metal 790, paper 500, plastic 921); 1660 images of catch-all, food/vegetation and textile folders were **not** trained on and are used only to measure review routing. "Miscellaneous Trash" is not treated as a material. Licence conflict (UCI: CC BY 4.0; authors' GitHub: CC BY-NC-SA 4.0) is unresolved. Cite: Single, Iranmanesh and Raad (2023), *Information* 14(12):633, https://doi.org/10.3390/info14120633. Labels are the authors' and were not audited. Pipeline checks: SHA-256 denylist of TrashNet images (0 matches), group-aware split, byte-duplicate leakage check.

## Evaluation (held-out group-aware test split, n = 516, evaluated once)
| | |
|---|---|
| Accuracy | **0.895** (95% CI 0.855-0.931) |
| Macro-F1 | **0.896** (95% CI 0.851-0.929) |
| Calibration (ECE) | 0.036; mean confidence 0.907 vs accuracy 0.895 |
| With the review rule | 83% auto-accepted at 93.5% accuracy; 48% of errors sent to review |
| Best baseline (hand-crafted features) | macro-F1 0.636 |
| Latency (2 CPU cores, bytes to decision) | p50 75 ms, p95 90 ms |

**Review rule:** needs review when calibrated confidence < 0.75 or similarity to the training images < 0.620.

## Known weaknesses
- **Single-site data, not field data.** All training and test images come from one Australian facility. Accuracy for Indian municipal waste, Hyderabad lighting, packaging and clutter is **unknown** until the field evaluation in `docs/ml/field-evaluation-protocol.md` is run.
- Weakest class on test: **plastic** (F1 0.86). The most frequent confusions on the test split: plastic predicted as glass (11 images).
- Out-of-scope waste (catch-all, food, vegetation, textile folders): 79.7% of 1660 images were sent to review; the rest would have been given a material label.
- Worst synthetic stress: **occlusion (~30% area)** (accuracy 0.62, mean confidence 0.80; auto-accepted accuracy 0.73).
- Only 5 classes: items outside them can be forced into one (mitigated, not solved, by the novelty gate; tested on the out-of-scope folders above and a ten-input smoke set).
- Generalisation gap: train (in-sample) macro-F1 0.98 vs held-out 0.90.
- Residual near-duplicate similarity across the split (see report section 1), so the test score may be slightly optimistic.
- Collected in one place and time; Indian municipal waste (packaging, materials, regional streams) is not represented.

## Ethical and privacy notes
No person was looked for in the training photographs and none is expected, but they were not audited (`personal_data: not assessed` in the manifest). Inference inputs are user photographs that may contain people or places; the upload
pipeline strips EXIF/GPS metadata and stores images under the platform's access rules. Predictions must be shown as suggestions with their confidence.

## Recommendations
Collect and label local field images (with consent), route low-confidence cases to reviewers, monitor review/correction rates
for drift, re-estimate the review threshold on field data before relying on it, and retrain from reviewed corrections.

## Provenance
git `430e027daf5f`; config SHA-256 `120bce10aad632ec...`; dataset digest `59fabef99c26bb25...`; `model.json` SHA-256 `580d6cce168a55f8...`.
Registry entry: `ml/model_registry/waste_classification/2.0.0.yaml`.
