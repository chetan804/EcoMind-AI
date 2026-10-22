# Mendeley Recyclable Waste Image Dataset: candidate evaluation and experiment plan

**Status 2026-10-22: BLOCKED AT DOWNLOAD. No image has been inspected, no model has been trained, and there are no
results.** Everything in "Verified so far" comes from the publisher's metadata. Everything under "Plan" is written
**before** any data was seen, so the criteria cannot be tuned to the outcome.

This candidate is separate from RealWaste. The RealWaste-only experiment (model `2.0.0`, `datasets/manifests/realwaste-2.0.yaml`,
`docs/ml/reports/waste-classification-2.0.0.*`) is not modified by anything here.

## Verified so far (publisher's public API and landing page, read 2026-10-22)
| Item | Value |
|---|---|
| Title / contributor | Recyclable Waste Image Dataset / João Alves |
| Version, DOI, published | Version 1, 10.17632/h5pxbsdz4m.1, 2026-06-04 |
| Landing page | https://data.mendeley.com/datasets/h5pxbsdz4m/1 |
| Licence | **CC BY 4.0** (`data_licence`: Creative Commons Attribution 4.0 International). The publisher's licence text adds that further permission may be needed for content identified as belonging to a third party |
| Provenance (publisher's description) | Subset of a master's dissertation dataset (ISEP, Porto, "Uso da Inteligência Artificial nos Processos de Pré-Reciclagem"). The author's full dataset had 8,068 images that also contained public third-party datasets; **this release keeps only 1,000 images photographed by the author** in municipal waste facilities, urban public spaces and homes |
| Classes | paper, cardboard, plastic, metal, glass (five; no out-of-scope class) |
| Size | zip "Recyclable Waste Image Dataset.zip", API size 1,707,542,607 bytes (page: 1.59 GB) |
| Per-file listing | the API lists every file with its SHA-256 and size; names look like `CWMF_Cardboard  (1).jpg` and `UHW_Plastic (95).jpg` (a site prefix, the class, a running number) |
| Folder layout, image counts per class, readability, duplicates, overlap | **NOT VERIFIED: needs the files** |

Not established: that the 1,000 images contain no third-party content (the publisher says so; the files were not
checked and the licence text itself warns about third-party content); that nobody is identifiable in them; that no
GPS metadata is present. `datasets/manifests/mendeley-recyclable-1.0.yaml` records these as open questions and keeps
`release_allowed: false`.

## The blocker
`data.mendeley.com` is not reachable from the build sandbox (only GitHub, PyPI and npm are). No dataset file was attached to
the session. **Owner action:** put either the zip or the extracted folder into the workspace (for example
`datasets/external/mendeley-recyclable-1.0/`, which is git-ignored), and save the publisher's list next to it:
`curl -o mendeley-h5pxbsdz4m.json https://data.mendeley.com/public-api/datasets/h5pxbsdz4m`. Then run the inspection below.

## Step 1: inspection (implemented and unit-tested; not yet run on the real files)
```bash
PYTHONPATH=. python -m ml.waste_classification.data.inspect_candidate \
  --root datasets/external/mendeley-recyclable-1.0 --source-json mendeley-h5pxbsdz4m.json \
  --expected-images 1000 --realwaste-root datasets/external/realwaste-src/RealWaste \
  --out docs/ml/dataset-research/inspections/mendeley-recyclable-1.0.inspection.json
```
It reports structure, class labels recovered from names and folders (anything unrecoverable or contradictory is a problem),
readability (every pixel decoded), image sizes, EXIF GPS, exact duplicates, byte-identity with the RealWaste table and with
the prohibited TrashNet/TrashBox hashes, perceptual-hash near-duplicates inside the set and against RealWaste, and a
comparison with the publisher's per-file SHA-256 list. `validation_passed` is true only when **no** problem is listed.
Training must not start unless it is true. A failure is handled by excluding the named files in the manifest and re-running,
never by editing the report.

## Step 2: manifest
Fill in `images.files_digest`, the per-class counts and the overlap-check results in `mendeley-recyclable-1.0.yaml`. Until the
digest exists the provenance gate refuses the manifest (tested). The licence status stays as recorded unless the contributor
answers the open questions in writing.

## Step 3: experiment, pre-declared (not started)
* **Version and files.** `waste-classification 3.0.0`: config `ml/configs/waste_classification_realwaste_mendeley.yaml`,
  artifacts `ml/artifacts/waste_classification/3.0.0/`, registry `ml/model_registry/waste_classification/3.0.0.yaml`, report
  `docs/ml/reports/waste-classification-3.0.0.{json,md}`. Nothing under `2.0.0` is overwritten.
* **Code still to write (after Step 1 shows what the files look like):** a `--config` option in `training/train.py`, a loader
  that reads the class from the file name for this dataset and merges two verified manifests, and per-source reporting.
  It is deliberately not written yet: its details depend on the folder layout, which is unknown.
* **Evaluation 0 (no training).** The existing 2.0.0 weights are scored on all Mendeley images: the first genuine
  external check of the RealWaste-only model. It is reported separately and is not the 3.0.0 result.
* **Splits.** Near-duplicates are clustered **jointly across both datasets** (a Mendeley image near-identical to a RealWaste
  image shares a group, so it can never straddle train and test). Stratified group folds, seed 42, test fold 0, validation fold 1,
  as in 2.0.0. Class counts per split are reported. As an extra check, one run holds out an entire Mendeley site prefix.
* **Selection and calibration.** Unchanged from 2.0.0 (grouped CV on the train split, 1-SE rule, temperature and review
  thresholds on validation only, test scored once).
* **Reported.** Per-class precision, recall, F1, the confusion matrix, ECE and reliability, selective accuracy, robustness, and
  the out-of-scope review rate. Metrics are given **separately** for the RealWaste part of the test split, the Mendeley part,
  and pooled, so a gain on one cannot hide a loss on the other.
* **Out-of-scope.** Mendeley has no out-of-scope class. The criterion is measured on the same four RealWaste folders
  with no EcoMind class (food, vegetation, textile, miscellaneous), which are never trained on.
* **Acceptance.** The thresholds in `ml/configs/waste_classification.yaml` are copied unchanged, including
  `min_out_of_scope_review_rate: 0.90` and the Hyderabad field evaluation. They are not relaxed to suit this dataset. The result of
  2.0.0 on that criterion was 0.797 (fail).
* **Licence.** A model trained on RealWaste plus this dataset inherits RealWaste's conflicting licence status, so it stays
  research-only and `approved_for_activation` stays false, whatever the numbers.
* **Expected limitation (stated now).** About 200 images per class means a Mendeley test share of roughly 170 images, so its
  confidence intervals will be wide. The photographs are from Portugal: this is **not** Hyderabad field data and says nothing about
  Hyderabad accuracy.

## What exists in the repository now
`ml/waste_classification/data/inspect_candidate.py` and `ml/tests/test_inspect_candidate.py` (17 tests on synthetic images:
unreadable, unmapped and contradictory labels, prohibited and RealWaste overlap, exact and near duplicates, GPS, class minimum,
publisher-hash mismatches, zip versus folder); `datasets/manifests/mendeley-recyclable-1.0.yaml` and
`ml/tests/test_mendeley_manifest.py` (6 tests: the pending manifest is refused by the gate, the licence evidence is recorded,
release stays blocked, RealWaste is untouched).
