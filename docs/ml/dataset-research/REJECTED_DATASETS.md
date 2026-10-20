# Rejected, deferred and blocked datasets

Compiled 2026-10-20. "Rejected" means *not used for any trained or released model*; "deferred" means a plausible candidate that
could not be obtained or verified yet. Reasons are stated as evidence, not opinion.

| Dataset | Status | Reason (evidence) | What would change the decision |
|---|---|---|---|
| TrashBox (`nikhilvenkatkumsetty/TrashBox`, `…-testandvalid`) | **Rejected for training and evaluation; not downloaded** | No licence file and no GitHub licence field (all rights reserved by default). README totals disagree with the repository (e-waste 2,883 vs 2,405 images in the sub-folder copy; medical 2,010 vs 1,565). Every image is stored twice, which doubles the leakage risk if both trees were read | Written permission or a licence statement from the authors (the repository's `CITATION.cff` gives a contact route) |
| RealWaste as **training data of a released model** | **Rejected** (evaluation and one labelled experiment are allowed) | CC BY-NC-SA 4.0 (README). NonCommercial and ShareAlike are incompatible with default activation and redistribution | Owner decision that the deployment is non-commercial research and that ShareAlike is acceptable, or permission from the authors. Until then a model trained on it is an experiment, never an activated version |
| spotgarbage-GINI | Rejected | No licence; single-class (garbage / not garbage) so it cannot supply material labels | A licence and a multi-class relabelling |
| NawanolT/Garbage-Dataset | Rejected | MIT repository of 6 KB containing no images | The authors publishing the images with a licence |
| AgaMiko/waste-datasets-review | Not a dataset | A catalogue of other datasets (no licence); used only as a pointer list | — |
| TACO | **Deferred** | Licence audit done (`TACO_LICENCE_AUDIT.md`): 0 of 1,500 images carry a verifiable commercial-use licence in the annotation file (null / bare "CC" / ODbL), and the images are fetched from hosts unreachable here; labels are object-level (detection/segmentation) and need a documented conversion to material classes | Owner-run source-licence verification (`scripts/ml/taco_flickr_verify.py`) and image import; the conversion rule must be agreed before use |
| detect-waste (pooled data) | Deferred | The repository contains code and annotation files, not the pooled images; the constituent datasets keep their own licences | Obtain each constituent from its own source and audit it |
| ZeroWaste | Deferred / unverified | Project site unreachable; a search snippet lists CC BY-NC (would be non-commercial even if reachable) | Access plus the licence text |
| Kaggle Garbage Classification V2, waste_pictures | Deferred / unverified | Kaggle is not reachable from the sandbox and the licence could not be read; these would add battery, clothes, shoes and biological classes | Download by the owner with the licence text and a provenance check |
| RecyBat24 | Deferred / unverified | Not reachable; would add a `battery` class if licensed for the use | Access plus licence |
| GlobalWasteData | Not used | A merged secondary collection; its licence table is secondhand evidence and merged labels hide conflicts | Check each constituent at its source instead |
| Moratuwa series (UCloudMl) | Rejected for forecasting | Day and month appear swapped for days ≤ 12 (series ends 2018-12-11), so weekly totals would be wrong | A corrected source file |
| Homagama series (UCloudMl) | Rejected for forecasting | 126 of 362 weeks would need interpolation, above the 25% gate | More complete records |
| Kerawalapitiya tickets (UCloudMl) | Not a forecasting series | Per-vehicle tickets with no incident labels | Labelled incidents for any supervised use |

## Taxonomy classes deliberately *not* added

`organic`, `textile`, `e_waste`, `medical`, `battery`: the only labelled images found for the first two are RealWaste
(non-commercial) and for the next two TrashBox (unlicensed); none was found for `battery` that could be reached. The
classifier therefore has no such classes. Images of those materials are expected to be sent to **review**; the measured share
is in the selection report (96% of RealWaste food, vegetation and textile images are sent to review by the released model).
