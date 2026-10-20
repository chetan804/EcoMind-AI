# TACO licence audit (production policy)

Audited 2026-10-20 from `data/annotations.json` of `pedropro/TACO` (branch `master`, commit
`70479ad9adc3da971a8ae75ac97eb1026910eec7`, committed 2026-10-20T14:46:48Z; file SHA-256
`812c2e3f0d336b437f276597715de2abb08bb8a641599c45f593d233ec66457b`, fetched through
`codeload.github.com`). Re-run with `python scripts/ml/taco_licence.py audit --download`; the machine-readable
result is `taco-licence-audit.json` (counts only, no image URLs).

## Policy

A production or released model may use an image only if its licence is **known to allow commercial use**:
CC BY, CC BY-SA, CC0 or public domain. NC, ND, unknown and unspecified licences are excluded. ODbL is excluded
until a legal opinion says what it means for a trained model (database licence with share-alike duties); it can
be enabled on purpose with `--allow-odbl`. Attribution (CC BY, CC BY-SA) is recorded in the import manifest, not
dropped.

## Result (official 1,500-image file)

| `license` value in `annotations.json` | Images | Objects | Decision |
|---|---:|---:|---|
| `null` (not recorded) | 715 | 2,152 | excluded: unknown |
| `"CC"` (no variant) | 319 | 1,176 | excluded: BY, NC, ND or SA is not stated, so commercial use cannot be shown |
| `"ODBL (c) OpenLitterMap & Contributors"` | 466 | 1,456 | excluded: ODbL, legal opinion needed |
| CC BY / CC BY-SA / CC0 / public domain | **0** | **0** | |

**Eligible images from the annotation file alone: 0 of 1,500.** The unofficial annotation file (3,831 images)
has the same two kinds of strings (`"CC"` 2,399, ODbL 1,432) and nothing eligible either.

Corrections to earlier notes: the catalogue said the annotations were "CC BY 4.0 per README". The README of
the audited commit contains no licence statement, so that is not confirmed here; the repository code is MIT
(the `LICENSE` file). The per-image field in the data is the evidence that was audited, and it is not enough.

## What would make images usable (owner-run; the sandbox cannot reach the image hosts or Flickr)

1,034 of the 1,500 images have a Flickr photo id in their file name (715 with no licence recorded and 319 with
the bare `"CC"`); the 466 OpenLitterMap images have none.

1. Get a Flickr API key and run
   `FLICKR_API_KEY=... python scripts/ml/taco_flickr_verify.py --annotations data/annotations.json`.
   It records each photo's licence **as stated by Flickr** with an evidence URL and date in
   `datasets/external/taco/verification.csv` (git-ignored). Photos Flickr no longer returns stay excluded.
2. `python scripts/ml/taco_licence.py audit --annotations data/annotations.json` re-classifies using that file
   and writes `datasets/external/taco/eligible_images.csv`.
3. `python scripts/ml/taco_licence.py import` downloads only the eligible images (https only, JPEG/PNG check,
   25 MB cap, resumable) into `datasets/external/taco/images_root/` with SHA-256, licence and source URL per
   file in `import_manifest.json`, and writes a COCO subset restricted to those images.
4. Before training: agree and document the rule that converts TACO's 60 object categories (28 super-categories)
   into the product's material classes (not done), record a dataset manifest in `datasets/manifests/`, split by
   source photo to avoid leakage, and evaluate honestly.

Neither Flickr script has been run against the live services (no key, no access here). They are tested with
mocked transports (`tests/contract/test_taco_scripts.py`, 27 tests): licence classification, the evidence
rules, the eligible list, the import (path safety, non-image rejection, resume, dry run) and the Flickr lookup.
Flickr licence ids 0 to 10 follow the Flickr API documentation as quoted in public references; CC 4.0 ids (11
and up) are deliberately left unmapped and excluded.

## Other datasets under the same policy

- **RealWaste** (CC BY-NC-SA 4.0) and **TrashBox** (no licence): never used in a production or released model.
  RealWaste stays an evaluation/experiment artefact (`datasets/manifests/realwaste-1.0.yaml`); a model trained
  on it may exist only as a labelled, inactive research artefact. TrashBox was not downloaded.
- **TrashNet** (MIT) remains the only dataset behind the candidate model `waste_classification 1.0.0`.
