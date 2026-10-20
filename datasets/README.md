# Datasets

Data used to train and evaluate models. **Data files are never committed**: `raw/`, `interim/`, `processed/` and `external/` are ignored by Git (only `.gitkeep` is tracked). What is tracked is the *description* of data.

| Directory | Contents |
|---|---|
| `raw/` | Immutable originals as received. |
| `interim/` | Intermediate, reproducible transformations. |
| `processed/` | Final model-ready data (train/validation/test splits). |
| `external/` | Third-party datasets, with their licence recorded in a manifest. |
| `manifests/` | **Tracked** YAML manifests, one per dataset version: source/URL, licence, collection date, size, file hashes, label mapping, split definition, known limitations and whether it contains personal data. |

Rules: record provenance and licence before using any dataset; do not store personal or private data here; large data goes to external storage referenced by its manifest (and hash). No datasets have been added yet.
