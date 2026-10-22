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

1. Get your own free Flickr API key and run (from a machine that can reach `api.flickr.com`)
   `FLICKR_API_KEY=... python scripts/ml/taco_flickr_verify.py fetch --annotations data/annotations.json`.
   For every image whose file name is a Flickr photo id it asks `flickr.photos.getInfo` for the licence and the
   author, after first reading Flickr's own licence table (`flickr.photos.licenses.getInfo`, so the 2025
   Creative Commons 4.0 ids are not guessed). The licence text is derived from the licence's
   `creativecommons.org` URL; anything else (all rights reserved, "no known copyright restrictions", an unknown
   id) is recorded as *unmapped* and stays excluded, and so does a photo Flickr no longer returns (error 1 or 2).
   Outputs, both git-ignored: `datasets/external/taco/verification.csv` (licence, licence id and URL, evidence
   URL, photo page, author, SHA-256 of Flickr's raw answer, date, who ran it) and
   `datasets/external/taco/flickr_raw/` (Flickr's raw answer per photo plus the licence table; it names
   photographers, so it is not committed). Transient errors are retried; photos that never answered are not
   recorded, so re-running the same command asks only for those. About 1,034 calls at the default pause of 1.1 s
   is roughly 20 minutes (Flickr allows 3,600 calls per hour per key).
2. `python scripts/ml/taco_flickr_verify.py validate --annotations data/annotations.json --raw-dir`
   checks the file without any network and exits 1 if a row fails (see "What validation proves").
3. `python scripts/ml/taco_licence.py audit --annotations data/annotations.json`
   re-classifies using that file (rows that fail validation are ignored and counted in
   `verification_rows_rejected`; the raw folder is used when it exists) and writes
   `datasets/external/taco/eligible_images.csv`, which now carries the author and photo page of each image.
4. `python scripts/ml/taco_licence.py import` downloads only the eligible images (https only, JPEG/PNG check,
   25 MB cap, resumable) into `datasets/external/taco/images_root/` with SHA-256, licence and source URL per
   file in `import_manifest.json`, and writes a COCO subset restricted to those images.
5. Before training: agree and document the rule that converts TACO's 60 object categories (28 super-categories)
   into the product's material classes (not done), record a dataset manifest in `datasets/manifests/`, split by
   source photo to avoid leakage, and evaluate honestly.

### Running the verification on another machine

The tool needs only Python 3.11+ (standard library), `data/annotations.json` from the TACO repository and a Flickr
key. Copy `scripts/ml/taco_flickr_verify.py` and `scripts/ml/taco_evidence.py` together, run `fetch`, then bring
back `verification.csv` **and** the `flickr_raw/` folder (keep both with the dataset record), place them under
`datasets/external/taco/`, and run `validate --raw-dir` and the audit here. Do not send the API key.

### What validation proves, and what it does not

`validate` and the audit check that every row is for the right image (evidence URL built from the image's own
Flickr photo id), that the licence text follows from the licence URL, that the licence id and URL agree with
Flickr's documented table (ids 1 to 6, 9, 10) or, with the raw folder, with the saved live table, that the date
is valid and not in the future, that the author is named for CC BY / BY-SA, that no image appears twice, and,
with the raw folder, that each row equals Flickr's saved answer (SHA-256, licence id, author, photo page).
That catches typing errors, a row pasted onto the wrong image, a licence relabelled by hand, and edits made
after the fetch. It does **not** prove that the answers came from Flickr: someone who can write both the CSV and
the raw folder can forge both. The protection is procedural: the owner runs `fetch` with their own key and
keeps the raw folder with the dataset record. Nothing here is legal advice; CC BY and CC BY-SA also oblige you
to credit the author (the eligible list carries it), and CC BY-SA obliges share-alike on adapted material, which
should be considered before any dataset or model is redistributed.

### Honest status of the scripts

The Flickr tool has never run against the live service (no key, no access from the build environment), so no
real Flickr answer has been seen by the author; the answer shapes follow the Flickr API documentation. Tests use
a mocked transport with synthetic answers (`tests/contract/test_taco_evidence.py`, 44 tests, and
`tests/contract/test_taco_scripts.py`, 25 tests): licence derivation, the rules above with a mutation check
that removing the evidence-URL or SHA-256 rule fails tests, retry and resume, an invalid API key, a missing
licence table, and the audit ignoring forged rows. Rows written by the older version of this tool (columns
`image_id,licence,evidence_url,verified_on,verified_by`, no `source`) and rows typed by hand are still accepted
by the audit under the old rules (evidence URL and date required).

## Other datasets under the same policy

- **RealWaste** (licence conflict: UCI CC BY 4.0 vs authors' GitHub CC BY-NC-SA 4.0) and **TrashBox** (no
  licence): never used in a production or released model. RealWaste is now the research training set
  (`datasets/manifests/realwaste-2.0.yaml`); a model trained on it is a labelled, inactive research artefact.
  TrashBox was downloaded once on 2026-10-21 for a research experiment and is now prohibited.
- **TrashNet** is prohibited (2026-10-22). The model trained on it, `waste_classification 1.0.0`, is withdrawn;
  the candidate is now `2.0.0` (RealWaste only).
