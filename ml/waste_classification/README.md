# Waste classification

**Status:** not started. No dataset, no training code, no trained model.

## Contract (target)
- **Input:** one RGB image prepared by `ml/common/preprocessing/images.py` (square size set in `configs/`).
- **Output:** `object_label` (the identified object/product), `object_confidence`, `material_category` (a `material_categories.code` from the backend) and `material_confidence`. Disposal guidance is **not** a model output: it is looked up from the sorting guide by material category.
- **Uncertainty:** predictions below the configured confidence threshold are returned as "needs review", never as a confident label.
- **Human review:** reviewers confirm, correct or reject predictions (`classification_predictions.review_status`); corrections are candidates for the next training set after a data-quality check.

## Required before any model is used
Dataset provenance and licence recorded in a `datasets/manifests/` manifest; label mapping to `material_categories`; data validation; train/validation/test split definition; reproducible training config; evaluation report with metrics and confusion matrix; registry manifest with artifact hashes; model card in `docs/ml/model-cards/`.
