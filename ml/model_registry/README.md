# Model registry

Tracked, human-reviewable **manifests** that describe each released model version. Model files themselves live in `ml/artifacts/` (ignored by Git) or external storage.

A manifest (`<capability>/<version>.yaml`) records: model name and version, framework and version, artifact file names with SHA-256 hashes, dataset manifest reference, preprocessing config, evaluation metrics and report location, training code commit, and the date. The backend verifies the hashes before loading and mirrors name/version/metrics into `classification_model_versions` (and equivalents) when a version is activated.

No manifests exist yet because no model has been trained.
