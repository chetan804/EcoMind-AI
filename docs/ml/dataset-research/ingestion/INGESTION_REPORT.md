> **Updated 2026-10-22.** TrashNet and TrashBox are no longer ingested: they are prohibited and `data/fetch.py`
> does not download them. The TrashNet figures below describe the withdrawn 1.0.0 ingestion and are kept as
> history. The current ingestion is RealWaste 2.0 (`datasets/manifests/realwaste-2.0.yaml`, verified digest
> `59fabef9…432ef`, 4,752 files, 0 undecodable, 0 exact duplicates, 0 files byte-identical to a TrashNet image).

# Ingestion and validation report

**Run date:** 2026-10-20. **Host:** 2 CPU cores, ~3.9 GB RAM, ~18 GB free disk. **Code:** `ml/waste_classification/data/fetch.py`
(TrashNet and the backbones) and the commands below (RealWaste). All raw data live under `datasets/external/` which is
git-ignored; nothing in this report was copied into Git except the manifests and these text/JSON reports.

## Rules applied
- Pinned commits (never a branch name); sources limited to the allow-listed git hosts; no downloaded code was executed.
- Raw data are never modified; derived files (embeddings cache, splits) go under `ml/artifacts/` (git-ignored).
- Every image was decoded with the same validated loader used at serving time (`ml/common/preprocessing/images.py`: format
  allow-list, size cap, EXIF-aware); failures are listed, never skipped silently.
- Exact duplicates found by SHA-256 of the file bytes; near-duplicates by average-linkage clustering of EfficientNet-EdgeTPU-S
  embeddings at cosine similarity ≥ 0.70, **per class** (0.70 is above the 99th percentile of random same-class pairs
  on TrashNet; see `ml/configs/waste_classification.yaml`).
- Splits are group-aware: no near-duplicate group crosses train/validation/test (asserted in code).
- Model selection, calibration (temperature) and the review rule use train/validation only; test is read once.

## Results

| Dataset | Pinned version | Files | Decoded OK | Exact duplicate files | Content digest (SHA-256 over sorted `class/name sha256` lines) |
|---|---|---|---|---|---|
| TrashNet resized | `6fa2b878…` | 2,527 | 2,527 | 3 (2,524 distinct) | `73cfe75b6a3e1bf1d19632514006aad5c26944480f9364402003be9e567b5221` |
| RealWaste | `156e8e91…` | 4,752 | 4,752 | 0 | `59fabef99c26bb25afb86b718981e6fc6e04b6bcba6bd39de5834ee668f432ef` |
| RealWaste ∩ TrashNet | — | — | — | 0 exact overlap (checked by file SHA-256) | — |

Class distributions: TrashNet cardboard 403 / glass 501 / metal 410 / paper 594 / plastic 482 / trash 137;
RealWaste Cardboard 461 / Food Organics 411 / Glass 420 / Metal 790 / Miscellaneous Trash 495 / Paper 500 / Plastic 921 / Textile Trash 318 / Vegetation 436 (all match the sources' stated counts).

Image geometry: TrashNet 512×384 JPEG; RealWaste 524×524 JPEG (every file). No other size or format occurred.

### Leakage audit
| | TrashNet | RealWaste |
|---|---|---|
| Near-duplicate groups | 1,477 | 2,043 |
| Images in a multi-image group | 60.98% | 78.7% |
| Largest group | 35 | 72 |
| Split (train / validation / test) | 1,684 / 422 / 421 | 3,168 / 792 / 792 |
| Group straddling a split | none (asserted) | none (asserted) |

A random image-level split of either dataset would put near-copies of a test image in training and overstate accuracy; the
group-aware split is what makes the held-out numbers meaningful. RealWaste is more redundant than TrashNet, so its
held-out CIs are wide (≈ ±5 points) even with 792 test images.

### Cross-dataset evaluation (no leakage by construction)
The released model never saw RealWaste. All 4,752 images were scored; nothing was fitted on them. Result file:
`experiments/cross-dataset-realwaste.json`. Summary in `DATASET_SELECTION_REPORT.md`.

### Time series
Weekly aggregation, completeness rule, interpolation counts and exclusions per series are recorded in
`experiments/time-series-results.json` (chronological 70/30 split, seasonal-naive/naive/moving-average/SES/damped-Holt/Holt-Winters
baselines, seed 42).

## Reproduce (current pipeline, RealWaste 2.0)
```bash
python -m venv /tmp/venv-ml && /tmp/venv-ml/bin/pip install -r ml/requirements-dev.txt
# validates the manifest (fails closed), clones RealWaste at the pinned commit, verifies the content
# digest, and fetches the Coral backbones at their pinned commit
PYTHONPATH=. python -m ml.waste_classification.data.fetch
PYTHONPATH=. python -m ml.waste_classification.training.train      # provenance gate, split, model, report
PYTHONPATH=. python -m ml.waste_classification.evaluation.report   # figures, evaluation report, model card
```
The 1.0.0 reproduction commands (TrashNet, cross-dataset and multi-dataset scripts) were removed: those experiments
used prohibited data and the scripts now refuse to run (`ml/waste_classification/research/`). Their recorded results
under `experiments/` are marked withdrawn.
