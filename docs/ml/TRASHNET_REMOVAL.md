# TrashNet removal record (2026-10-22)

**Decision.** TrashNet, and every file that is byte-identical to a TrashNet image (819 files in TrashBox), is excluded from
every training, validation, test and release dataset. Reason: the project has no written permission for TrashNet's
photographs; the MIT file in `garythung/trashnet` covers the repository and states no provenance for the images. Re-admission
needs written permission from the rights holders, a licence record in a manifest, and a change to the denylist policy.

## What was found and what was done

| Area | Found | Action |
|---|---|---|
| Training code | the loader (`data/trashnet.py`), `fetch.py`, `train.py`, `report.py` and the config were TrashNet-specific | loader generalised (`data/imagefolder.py`), fetch downloads RealWaste and the denylist hashes only, config and report rewritten for a manifest-driven dataset |
| Manifests | `trashnet-1.0.yaml`, `trashbox-research-1.0.yaml`, `realwaste-1.0.yaml` | TrashNet and TrashBox marked QUARANTINED (kept only as records; the gate refuses them by name); RealWaste 1.0 marked superseded by `realwaste-2.0.yaml` |
| Denylist | none | `datasets/manifests/prohibited-sha256.txt`: 2,524 TrashNet file hashes (hashes only, no images); checked on every dataset load; 0 matches in RealWaste |
| Model registry | `1.0.0.yaml` (TrashNet model, status candidate) | `status: withdrawn`, `replaced_by: 2.0.0`; the 1.0.0 artifact directory is not present in this workspace |
| Reports, model card, experiment JSONs | 1.0.0 report, model card, ablation JSON, cross-dataset, multi-dataset and TrashBox experiments | WITHDRAWN banner / `withdrawn` key; numbers kept as history only |
| Experiment code | `research/{cross_dataset,multi_dataset_experiment,trashbox_experiment}.py` | tombstoned (`WITHDRAWN = True`; `main()` exits) |
| Caches | git-ignored embedding caches keyed to the TrashNet tree | checked on 2026-10-22: `ml/artifacts/_cache` holds only embeddings written by the 2.0.0 run (RealWaste), and no 1.0.0 artifact exists in this workspace. These directories are git-ignored and were never committed. Other developer machines may still hold old copies: delete `ml/artifacts/` and `datasets/external/trashnet*` there |
| UI and API text | hard-coded "studio photographs", "about 45%" and a six-class list with "Other waste" | removed; the API note and UI state that no field accuracy is known; the class list comes from the model |
| Backend | no approval gate before activation | `activate_model` refuses unless `model.json` has `release.approved_for_activation: true` (409 `model_not_approved`) |
| Tests | assertions that depended on the six-class TrashNet model | updated; new tests for provenance, prohibited data, leakage, label mapping, field evaluation and missing-model behaviour |
| Academic and project documents | abstract, results, methodology, literature survey, ethics statement, PAPER_READINESS, viva outline, project guide, roadmap, status, audit, limitations, traceability, requirements, README files | every TrashNet-dependent figure (0.867, 0.841, 0.031, 0.454, 0.514, 0.263, 64%, 95.5%, the TrashBox figures) removed or labelled WITHDRAWN; remaining mentions of TrashNet are statements that it is excluded, or history banners |

## Files that still name TrashNet, and why
`git grep -il trashnet` lists, apart from this file: the denylist and the quarantined manifests; the provenance code and its tests
(which must name what they refuse); the tombstoned research modules; the withdrawn 1.0.0 artifacts and experiment records;
and documents that state the exclusion. None of them reads TrashNet images or lets TrashNet data into a dataset. A reader who
needs the numbers of the withdrawn model can find them only in files whose first lines say WITHDRAWN.

## Not done
* Word exports in `docs/exports/` are regenerated from the Markdown sources.
* The preprocessing ablation was not re-run for 2.0.0.
* The git history still contains the old files and numbers; history is not rewritten.
* Whether TrashNet photographs were ever redistributed in a released artifact: none was released.
