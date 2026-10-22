# Hyderabad field-photo evaluation protocol

**Status: NOT STARTED. No field photograph has been collected and there are no field results.** This document is
the process the owner follows to collect a *separate, consented, held-out* evaluation set. Nothing in this
repository reports a field accuracy, and no number may be quoted as one until `field-evaluation-<version>.json`
exists and was produced by the command in section 9 from real photographs.

Why it is needed: every figure the classifier has so far comes from one Australian facility (RealWaste). That says
nothing about Hyderabad packaging, lighting, clutter or waste streams, and the acceptance criteria in
`ml/configs/waste_classification.yaml` require a passing field evaluation before any model can be approved
for activation (`docs/ml/evaluation-protocol.md`).

The field set is an **evaluation set only**. It is never used to train, to tune hyper-parameters, to choose the
temperature or the review thresholds. If it is ever used for training it stops being a test set, and a new one
must be collected.

## 1. Who decides (owner actions, not code)

| Step | Who | Evidence to keep (outside Git) |
|---|---|---|
| Approve the study and name the person accountable for the data | project owner | signed approval note |
| Written permission from every site where photographs are taken (municipal facility, transfer point, institution, shop) | owner, from the site manager | permission letter or e-mail; its reference goes in `permission_ref` |
| Ethics review if people other than the project team take part (volunteers, sanitation workers) | institution's ethics committee | approval number |
| Confirm which data-protection rules apply (for example India's Digital Personal Data Protection Act, 2023) and that this protocol satisfies them | owner, with the institution's legal adviser | written confirmation (not verified by this project) |

Do not start collecting before the first three rows are done.

## 2. Where to photograph

* Only at places that gave written permission. No private property, residences, hospitals or schools without it.
* Record a pseudonymous `site_id` (for example `site-01`). **Never store an address, GPS coordinate or the name of a
  person in the manifest.** Keep the real site list in the permission file, outside the dataset.
* Cover several kinds of place and several days: at least three sites and two different days, so one place or one
  afternoon cannot dominate the result.

## 3. What to photograph

| Group | Content | Minimum |
|---|---|---|
| In scope | one photograph per physical item, labelled `cardboard`, `glass`, `metal`, `paper` or `plastic` | **30 per class** (the gate refuses fewer); aim for 60 or more per class, 300 or more in all |
| Out of scope | items the model has no class for: food and vegetable waste, textiles, mixed or unidentifiable items, e-waste, anything hazardous (photograph only what is safe to handle) | labelled `out_of_scope`; aim for 100 or more |

With about 60 images per class the 95% interval on a class recall is roughly plus or minus 0.1 or more. Say so when
reporting; do not describe a small set as precise.

Vary on purpose: daylight and shade, evening, wet and dirty items, crushed items, different backgrounds (ground,
bins, sacks), different distances, and at least two phone models. Include the hard cases (glass bottle next to a
metal can, plastic film, laminated paper) in the proportion that they occur, not hidden and not exaggerated.

## 4. Capture rules

* One item in focus per photograph; no more than one photograph per physical item.
* Use the phone's normal camera, no filters, no beauty or HDR modes that change colours.
* Do not look at the classifier's answer while photographing or labelling.

## 5. Consent and privacy

* **No people in the frame.** If a person, a face, a number plate, a document, a delivery label or a house number
  is visible, delete the photograph. Do not blur and keep: delete.
* Remove EXIF and GPS metadata before the files leave the phone (the manifest records the SHA-256 of the stripped file).
* Anyone who is photographed or who contributes photographs (including staff) is told what the photographs are for,
  that taking part is voluntary, and how to withdraw. Record that in `consent_ref`. Use `no-people-in-frame` only
  for photographs that contain no person.
* Store the files on an encrypted drive with named access. Do not upload them to cloud services, messaging apps or
  third-party labelling tools. Do not commit them: `datasets/field/*` is git-ignored.
* Retention: the owner sets a date after which the originals are deleted, and records it. A contributor can ask for
  their photographs to be removed; remove the rows and re-run the evaluation.

## 6. Labelling

* Two people label every photograph independently. Disagreements are settled by a third person, or the photograph is
  excluded or labelled `out_of_scope`. Set `label_checked_by_two` to `yes` only when this happened.
* A label is a *material*, not an object: a plastic bottle is `plastic`. Mixed, ambiguous or composite items go to
  `out_of_scope`, never into the nearest class.

## 7. Manifest

A tab-separated file, one row per photograph, in `datasets/field/hyderabad/manifest.tsv` (git-ignored). Columns, all
required and non-empty:

`file`, `sha256`, `class`, `captured_on` (ISO date), `site_id`, `collector_id` (pseudonymous), `permission_ref`,
`consent_ref`, `privacy_check` (`yes`), `label_checked_by_two` (`yes`).

The gate (`ml/waste_classification/evaluation/field.py`) refuses the whole manifest, and lists every problem, when:
a column or value is missing; a permission record is `none`; the privacy or two-person label check is not `yes`; a file
is a duplicate; a file is byte-identical to a training image (leakage) or to a TrashNet image (prohibited); fewer than
the required number of images or fewer than 30 per class are present. It also refuses a file whose bytes do not match
its recorded SHA-256.

## 8. What stays out of this set

TrashNet, TrashBox, RealWaste and any image already used in training (checked by hash); photographs scraped from the
web or social media; photographs taken by members of the public without the notice in section 5.

## 9. Running the evaluation

After the classifier has been trained (`python -m ml.waste_classification.training.train`):

```
PYTHONPATH=. python -m ml.waste_classification.evaluation.field \
    --manifest datasets/field/hyderabad/manifest.tsv --images datasets/field/hyderabad/images
```

It writes `docs/ml/reports/field-evaluation-2.0.0.json` (per-class precision, recall and F1, confusion matrix,
accuracy of auto-accepted predictions with a Wilson interval, the share of out-of-scope photographs sent to review,
sites and dates, and the SHA-256 of the exact model weights). Re-run the (deterministic) training so the acceptance
block is re-evaluated: a field report is accepted only if it was measured on the same weights, and approval needs the
offline criteria **and** the field criteria (`acceptance.field` in the config: at least 300 images, macro-F1 0.75,
accuracy of auto-accepted predictions 0.90). If any criterion fails, the model stays inactive. Do not change the
criteria after seeing the result.

## 10. What to publish about it

Report the number of photographs per class and per site, the dates, the phones, who labelled, the full per-class
table and confusion matrix, the errors (look at them and describe them), the review rate, and the limits of the
sample. Do not report a single headline accuracy without its interval and sample size.

## 11. Checklist before the first photograph

- [ ] Owner approval and an accountable person named.
- [ ] Written permission from each site (`permission_ref` recorded).
- [ ] Ethics approval if volunteers or staff take part.
- [ ] Data-protection applicability confirmed in writing.
- [ ] Encrypted storage and a retention date set.
- [ ] Two labellers named; blind-labelling rule understood.
- [ ] Phones set up; EXIF and GPS stripping tested on a sample file.
