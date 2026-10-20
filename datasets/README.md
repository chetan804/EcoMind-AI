# Datasets

Data used to train and evaluate models. **Data files are never committed**: `raw/`, `interim/`, `processed/` and `external/` are ignored by Git (only `.gitkeep` is tracked). What is tracked is the *description* of data.

| Directory | Contents |
|---|---|
| `raw/` | Immutable originals as received. |
| `interim/` | Intermediate, reproducible transformations. |
| `processed/` | Final model-ready data (train/validation/test splits). |
| `external/` | Third-party datasets, with their licence recorded in a manifest. |
| `manifests/` | **Tracked** YAML manifests, one per dataset version: source/URL, licence, collection date, size, file hashes, label mapping, split definition, known limitations and whether it contains personal data. |

Rules: record provenance and licence before using any dataset; do not store personal or private data here; large data goes to external storage referenced by its manifest (and hash). Registered datasets: `manifests/trashnet-1.0.yaml` (TrashNet, MIT; fetched on demand by `python -m ml.waste_classification.data.fetch`) and `manifests/realwaste-1.0.yaml` (RealWaste, **CC BY-NC-SA 4.0: evaluation and experiments only, never redistributed**; fetch recipe in the manifest). The research catalogue, selection report and rejected list are in `docs/ml/dataset-research/`.

Production policy: only images with a licence that is known to allow commercial use (CC BY, CC BY-SA, CC0, public domain) may train a released model. TACO was audited under this rule and no image qualifies on the strength of its annotation file; the owner-run path is in `docs/ml/dataset-research/TACO_LICENCE_AUDIT.md`.
