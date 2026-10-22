# Dataset catalogue

**Compiled 2026-10-20.** Every statement is tagged by how it was established:

- **Verified** — read from the source itself (repository tree, README, licence file, git API) or computed from the downloaded files in this session.
- **Secondhand** — seen only in a search snippet or in another project's README; not confirmed at the source.
- **Unverified** — the source could not be reached from this sandbox (allow-list: github.com, api.github.com, codeload.github.com, pypi.org, files.pythonhosted.org, registry.npmjs.org; Kaggle, Hugging Face, Flickr, Google Cloud Storage and project web sites are not reachable).

Sizes, licences and counts are never filled in from memory. Where something is not known it says so. Machine-readable
version: [`dataset_manifest.yaml`](dataset_manifest.yaml). Decisions and experiments:
[`DATASET_SELECTION_REPORT.md`](DATASET_SELECTION_REPORT.md). Download/validation evidence:
[`ingestion/INGESTION_REPORT.md`](ingestion/INGESTION_REPORT.md). Rejected or deferred sources: [`REJECTED_DATASETS.md`](REJECTED_DATASETS.md).

The 17 attributes recorded per candidate (the project prompt's list was not available to this session in full, so this is the
working set): 1 name · 2 task · 3 source URL · 4 access date · 5 version/commit · 6 licence · 7 licence evidence · 8 size ·
9 label type and classes · 10 real or synthetic · 11 geography and capture setting · 12 image/data conditions (clutter,
occlusion, background) · 13 mapping to the project taxonomy · 14 reachable from the sandbox · 15 quality and leakage
findings · 16 decision · 17 main risk.

Project taxonomy (material classes of the released model): `cardboard, glass, metal, paper, plastic, trash`. Reserved but
**unsupported** (no legitimately licensed labelled data available): `organic, textile, e_waste, medical`, plus
`unknown`/review for anything else. Object or product identification is a separate task and is not attempted.

## A. Ingested, audited and used

### A1. TrashNet (resized) — waste image classification — **PROHIBITED since 2026-10-22; withdrawn model 1.0.0 only**

> **Excluded from every new training, validation, test and release dataset** because written permission for its photographs was not obtained. Only its SHA-256 digests are kept (`datasets/manifests/prohibited-sha256.txt`) so that copies can be found and refused. The audit below is the historical record. Anything measured on or trained with TrashNet is withdrawn.

| # | Attribute | Value |
|---|---|---|
| 1–3 | Name · task · URL | TrashNet · whole-image material classification · https://github.com/garythung/trashnet |
| 4–5 | Accessed · version | accessed 2026-10-20 · commit `6fa2b878c6c1b4304b91109070ce0edf9279bb31`; file `data/dataset-resized.zip`, 42,834,870 bytes, SHA-256 `0bf47279…07c2` (verified) |
| 6–7 | Licence · evidence | MIT, "Copyright (c) 2017 Gary Thung" (LICENSE file; its SHA-256 is in the manifest). The licence file covers the repository; it says nothing more about the provenance of the photographs |
| 8 | Size | 2,527 JPEG, 512×384 (verified by decoding); 3 exact-duplicate files (2,524 distinct SHA-256) |
| 9 | Labels | one material label per image, 6 classes: cardboard 403, glass 501, metal 410, paper 594, plastic 482, trash 137. No object label |
| 10–12 | Real? · where · conditions | real photographs, objects on a white posterboard in sunlight/room light, iPhone 7 Plus/5S/SE (per the README). Single item, plain background, no clutter, no occlusion |
| 13 | Mapping | identity (class = project class) |
| 14 | Reachable | yes (git) |
| 15 | Quality / leakage | 60.98% of images belong to a multi-image near-duplicate group (1,477 groups, largest 35, cosine ≥ 0.70 on S embeddings, per class). Random splits would leak; the project uses group-aware splits. Labels not audited |
| 16 | Decision | **PROHIBITED / quarantined.** Withdrawn model 1.0.0 was trained on it. Manifest kept as a record only: `datasets/manifests/trashnet-1.0.yaml` (the provenance gate refuses it) |
| 17 | Main risk | Studio-style images: the model measured here does **not** transfer to real facility photos (see selection report: 0.45 accuracy on RealWaste) |

### A2. RealWaste — waste image classification — **PRIMARY training candidate, research-only until the licence conflict is resolved**
| # | Attribute | Value |
|---|---|---|
| 1–3 | Name · task · URL | RealWaste · whole-image material classification · https://github.com/sam-single/realwaste |
| 4–5 | Accessed · version | 2026-10-20 · commit `156e8e9154eeb163df30fcfd767f55b19633bb06` (2024-04-14); README SHA-256 `e812725f…e1b1` |
| 6–7 | Licence · evidence | **CONFLICTING.** UCI dataset page (read 2026-10-22): **CC BY 4.0**, DOI 10.24432/C5SS4G. Authors' GitHub README: **CC BY-NC-SA 4.0** ("this dataset is licenced under CC BY-NC-SA 4.0"); no LICENSE file, GitHub licence field empty. The owner reports IEEE DataPort also says CC BY-NC-SA 4.0 (not verified here). Treated as the more restrictive terms until the authors confirm in writing which applies to the exact version used |
| 8 | Size | 4,752 JPEG, all 524×524 (every file decoded, 0 failures), 688,308,374 bytes; no exact duplicates; 0 exact overlap with TrashNet (re-checked 2026-10-22 against the digest denylist) |
| 9 | Labels | one label per image, 9 classes: Cardboard 461, Food Organics 411, Glass 420, Metal 790, Miscellaneous Trash 495, Paper 500, Plastic 921, Textile Trash 318, Vegetation 436 (counts match the README) |
| 10–12 | Real? · where · conditions | real photographs of waste received at the Whyte's Gully facility, Wollongong NSW, Australia (README). Realistic backgrounds; capture protocol not documented in the README |
| 13 | Mapping | Cardboard/Glass/Metal/Paper/Plastic → same name (exact). **Miscellaneous Trash, Food Organics, Vegetation and Textile Trash → no class** (`maps_to: null`): never trained on, used only as out-of-scope input to measure review routing. "Miscellaneous" is not a material |
| 14 | Reachable | yes (git; 1.3 GB clone) |
| 15 | Quality / leakage | 78.7% of images lie in a multi-image near-duplicate group (2,043 groups, largest 72). Splits are group-aware. Labels not audited |
| 16 | Decision | **Train (5 classes, research-only), never redistribute images, no released or activated model until the licence is confirmed in writing and the field evaluation passes.** Manifest: `datasets/manifests/realwaste-2.0.yaml` (supersedes `realwaste-1.0.yaml`) |
| 17 | Main risk | Unresolved licence (NonCommercial + ShareAlike if the GitHub terms apply); single site in Australia (Indian waste not represented); not verified that the UCI zip is byte-identical to the GitHub copy (file sizes of five files and all class counts match) |

### A3. Municipal solid-waste time series (UCloudMl/solid-waste-prediction) — forecasting and anomaly experiments
| # | Attribute | Value |
|---|---|---|
| 1–3 | Name · task · URL | Weekly waste totals · fill/volume forecasting, anomaly experiments · https://github.com/UCloudMl/solid-waste-prediction |
| 4–5 | Accessed · version | commit `6ff6b1a073e7acbe7725150119a74c5f2fba26d2` (2022-12-04) |
| 6–7 | Licence · evidence | Repository MIT (LICENSE, "Copyright (c) 2022 Ivantha"). **The licence of the underlying municipal/open-data records is not stated: unverified.** Cite Mudannayake et al., IEEE Access, 2022 (as recorded in `ml/time_series/data.py`) |
| 8 | Size | Ticket rows: Boralesgamuwa 2,988, Dehiwala 3,583, Homagama 2,729, Moratuwa 6,691, Kerawalapitiya 92,164 (per-vehicle tickets), Austin 5,591, Ballarat 3,891 |
| 9 | Labels | daily net weight (kg) with a date; no anomaly labels |
| 10–12 | Real? · where | real municipal records: Sri Lanka (4 councils + a transfer station), Austin TX USA, Ballarat Australia |
| 13 | Mapping | weekly totals (Monday start), operating-weekday completeness rule, ≤25% interpolated |
| 14 | Reachable | yes (git) |
| 15 | Quality | day coverage 0.72–0.94 across the five series with a forecast audit; Moratuwa excluded (day/month swapped for days ≤ 12); Homagama excluded (126 of 362 weeks would need interpolation, above the 25% gate); audit in `experiments/time-series-results.json` |
| 16 | Decision | **Use for benchmarking the forecasting engine** (Austin and Ballarat imported as labelled *reference* series; held-out chronological test; every model compared with naive). Kerawalapitiya: anomaly experiments only. **Not** a source of the platform's own volumes |
| 17 | Main risk | Different cities and waste systems from the target deployment; licence of records unverified |

Results: Austin Holt-Winters MAE = 0.804 × naive, Ballarat 0.731 × naive; Boralesgamuwa and Dehiwala: naive was best on the development backtest (no model beats the baseline there, and the report says so).

### A4. KSU waste-collection routes — route-order validation
Source `kamthornsa/ksu-waste-collection-dataset`, commit `1653571de51c79058548fd7185980b4ef80ed8ab`, **CC BY 4.0** (recorded when the route validation was built; re-check the repository before redistributing any derived file; see `docs/ml/dataset-research/experiments/route-validation-ksu.json` and `scripts/ml/ksu_route_validation.py`). Observed routes are 1.096 × the exact optimum on the validation days; the project's heuristic matched the optimum. Used for validating the route-ordering algorithm, not for ML training.

### A5. Mendeley "Recyclable Waste Image Dataset" (ISEP, Porto) — **CANDIDATE, pending download; nothing trained**
Mendeley Data v1, DOI 10.17632/h5pxbsdz4m.1, published 2026-06-04, contributor João Alves. **Licence CC BY 4.0** (publisher's API `data_licence` and landing page, read 2026-10-22; the licence text warns that third-party content may need further permission). 1,000 author-photographed images in five classes (paper, cardboard, plastic, metal, glass), taken in waste facilities, public spaces and homes in Portugal; the author's full 8,068-image set also contained third-party datasets, which are **not** in this release (per the publisher; not verified from the files). The files could not be downloaded here, so structure, per-class counts, readability, duplicates and overlap with RealWaste and the prohibited hashes are **unverified**. Manifest `datasets/manifests/mendeley-recyclable-1.0.yaml` (fails the provenance gate until a files digest exists); plan and blocker: [`mendeley-recyclable-experiment-plan.md`](mendeley-recyclable-experiment-plan.md). Not Hyderabad data.

## B. Inspected at the source, not ingested

| Dataset | What was verified (2026-10-20) | Why not ingested |
|---|---|---|
| **TrashBox** — https://github.com/nikhilvenkatkumsetty/TrashBox (+ `…/TrashBox-testandvalid`) | HEAD `91e66aa8fee5b02c0613f0ee0e262707cc29342f`; 2.79 GB; README: 17,785 images, 7 classes (glass, plastic, metal, e-waste, cardboard, paper, medical); has `CITATION.cff`; **no licence file and no GitHub licence → all rights reserved by default**. The tree holds every image twice (flat and sub-folder copy). In the sub-folder copy e-waste = 2,405 images (README says 2,883) and medical = 1,565 (README says 2,010): the README totals do not match the repository | **No licence.** It is the only candidate with e-waste and medical classes. Using it needs the authors' written permission. **Downloaded 2026-10-21 for one research-only experiment** (owner reports verbal permission; nothing in writing): see `experiments/trashbox-experiment.json`, `datasets/manifests/trashbox-research-1.0.yaml` and the selection report §4b. 14,282 images in the used tree; 819 are byte-identical to TrashNet images |
| **TACO** — https://github.com/pedropro/TACO | code MIT, HEAD `29de1a9ba05a647b83a90f18d7772e20bb23d846`, 102 MB; per-image `license` strings in the annotations (null, bare "CC" or ODbL; no image verifiably CC BY/BY-SA/CC0 in the file, see `TACO_LICENCE_AUDIT.md`; the README of the audited commit states no licence) | Images are fetched from Flickr, which is unreachable here; object detection/segmentation labels would need an explicit, defensible conversion to material classes. Strong candidate if images are obtainable |
| **detect-waste** — https://github.com/wimlds-trojmiasto/detect-waste | MIT code, HEAD on `main` (87 MB); README says it merges 9 public datasets plus Google-image downloads and the unlabelled OpenLitterMap | Repository holds code and annotations, not the pooled images; each constituent has its own licence |
| **spotgarbage/spotgarbage-GINI** | no licence, 1.38 GB, single-class (garbage / not garbage) | No licence; single-class task |
| **NawanolT/Garbage-Dataset** | MIT, 6 KB: **contains no images** (13 class names; images are hosted elsewhere) | Nothing to ingest |
| **AgaMiko/waste-datasets-review** | catalogue only, no licence, 16.6 MB | Used as a pointer list; not a dataset |

## C. Not reachable (unverified — nothing about them is asserted as fact)

| Source | What is only secondhand | Note |
|---|---|---|
| ZeroWaste (detection/segmentation of conveyor-belt waste) | a search snippet lists CC BY-NC | project site not reachable; would be NC even if reachable |
| Kaggle "Garbage Classification V2" (sumn2u) | snippet: 19,762 images, 10 classes including battery, clothes, shoes, biological | Kaggle only (the GitHub path 404s); licence unverified |
| Kaggle "waste_pictures" (wangziang) | detect-waste README: ~24k images, 34 classes | Kaggle only; licence unverified |
| RecyBat24 (batteries, Nature Scientific Data) | snippet only | not reachable; would add a `battery` class if the licence allows |
| GlobalWasteData (arXiv 2602.07463) | snippet: merges many sets and lists their licences | a secondhand licence table is not evidence; each source must be checked |
| OpenLitterMap | detect-waste README: unlabelled images | not reachable; unlabelled |

## D. Supporting geographic, environmental and impact data

No dataset in these categories has been ingested. The platform does not ship coverage polygons, population or emission
coefficients because none have been sourced with a verified licence; the rewards ledger awards points only, and the analytics
module reports measured weights without converting them to CO₂ or similar claims. This is deliberate (no invented
coefficients). Candidates for a later step (not verified): national/municipal open waste statistics for India, and the
emission factors of a named, citable inventory.

## E. Anomaly detection data

No labelled operational anomaly data was found. The only operational record with per-vehicle tickets
(Kerawalapitiya, 92,164 rows) has **no incident labels**, so the detector's target is defined as *a weekly total whose
deviation from the median of the same week in previous years (or of the previous three weeks) is at least 3.5 robust standard
deviations (1.4826 × MAD of earlier errors only)* — a **suspected** anomaly, not a confirmed incident
(`docs/api/anomalies-api.md`). No precision or recall on real incidents is claimed; the benchmark reports only sensitivity to
*injected* anomalies and the alert rate on clean series. Alerts are labelled "suspected" in the product.
