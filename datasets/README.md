# Datasets

Data used to train and evaluate models. **Data files are never committed**: `raw/`, `interim/`, `processed/` and `external/` are ignored by Git (only `.gitkeep` is tracked). What is tracked is the *description* of data.

| Directory | Contents |
|---|---|
| `raw/` | Immutable originals as received. |
| `interim/` | Intermediate, reproducible transformations. |
| `processed/` | Final model-ready data (train/validation/test splits). |
| `external/` | Third-party datasets, with their licence recorded in a manifest. |
| `manifests/` | **Tracked** YAML manifests, one per dataset version: source/URL, licence, collection date, size, file hashes, label mapping, split definition, known limitations and whether it contains personal data. |

Rules: record provenance and licence before using any dataset; do not store personal or private data here; large data goes to external storage referenced by its manifest (and hash). Registered datasets: **`manifests/realwaste-2.0.yaml`** (RealWaste, the only training source; **licence conflicting: UCI says CC BY 4.0, the authors' GitHub says CC BY-NC-SA 4.0, so research use only and never redistributed until the authors confirm**; fetched by `python -m ml.waste_classification.data.fetch`; per-file hashes, labels, roles and groups in `manifests/realwaste-2.0.files.tsv`). **Prohibited, kept only as records:** `manifests/trashnet-1.0.yaml` (TrashNet: no written permission for the photographs) and `manifests/trashbox-research-1.0.yaml` (TrashBox: no licence, 819 files identical to TrashNet); their SHA-256 hashes are in `manifests/prohibited-sha256.txt` and the loader refuses any file that matches. `manifests/realwaste-1.0.yaml` is superseded. Hyderabad field photographs (`datasets/field/`, git-ignored) follow `docs/ml/field-evaluation-protocol.md`; none has been collected. The research catalogue, selection report and rejected list are in `docs/ml/dataset-research/`.

Production policy: only images with a licence that is known to allow commercial use (CC BY, CC BY-SA, CC0, public domain) may train a released model. TACO was audited under this rule and no image qualifies on the strength of its annotation file; the owner-run path is in `docs/ml/dataset-research/TACO_LICENCE_AUDIT.md`.
