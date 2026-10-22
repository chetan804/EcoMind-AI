# Ethics, data-licence and privacy statement (draft for the authors to confirm)

Status: **draft prepared from the repository on 2026-10-22.** It records what the code and documents show. It is not
legal advice and not an ethics-committee decision. Items marked **OWNER** need a person with authority.

## 1. Human participants
No user study, interview, survey or field pilot has been run, and the project has recorded no data from real
residents, collectors or officials. All accounts in the repository's tests and demonstrations are synthetic
(`example.org` addresses and generated names). A paper that reports usability, adoption or operational benefit would need
a study with ethics approval or a documented exemption from the authors' institution. **OWNER:** decide whether a study
will be run; none is claimed today.

## 2. Datasets used and what each licence permits

| Dataset | Use in this project | Licence evidence | Consequence |
|---|---|---|---|
| TrashNet (Thung and Yang) | training and in-domain test of the candidate classifier | MIT licence file in the source repository (copyright Gary Thung, 2017); the file covers the repository and says nothing about where the photographs came from | usable; cite the source; provenance of the photographs is not stated by the authors |
| RealWaste (Single et al.) | cross-dataset evaluation and a labelled experiment only | README states CC BY-NC-SA 4.0 (non-commercial, share-alike); the repository has no licence file | **no model trained on it is released or activated**; results may be reported with attribution and the non-commercial restriction |
| TrashBox | researched; an experiment record exists; **no released artefact depends on it** | no licence in the repository. The project owner reports verbal permission from the authors (2026-10-21), which is not documented in writing | do not train a released model or redistribute images until written permission or a licence exists. **OWNER:** obtain it in writing |
| TACO | tooling only | code MIT; annotations CC BY 4.0; images come from Flickr with per-image licence strings; 0 images were verifiably eligible | no TACO image is used |
| Public time series (Austin, Ballarat and Sri Lankan council tickets) | forecasting and anomaly benchmarks, shown in the product only as labelled reference data | the repository that supplied the records is MIT; **the licence of the underlying open-data records is not stated (unverified)** | confirm each city's open-data licence before publishing derived figures or redistributing the series |
| Kalasin University campus routes | route-ordering validation | CC BY 4.0 as recorded when the validation was built | re-check the repository before redistributing derived files |
| MapTiler Hyderabad dataset | **not installed** | free On-Prem tier is non-commercial or evaluation use with a user cap, and requires attribution "© MapTiler © OpenStreetMap contributors" | **OWNER:** download under the owner's account and confirm the terms; no tile data is in the repository |

The full audit trail, with access dates and commit hashes, is in `docs/ml/dataset-research/` and `datasets/manifests/`.
Raw datasets and model artefacts are git-ignored and are not redistributed by the repository.

## 3. Personal data the platform would hold if deployed
| Data | Where | Controls today | Gap |
|---|---|---|---|
| Name, e-mail, role, password hash (Argon2id), two-step secret and recovery-code hashes | `users` and related auth tables | RBAC, rate limits, lockout; contact e-mail of facilities is hidden from non-staff | no account-deletion or data-export feature |
| Sign-in sessions with IP address and user agent | auth tables | refresh tokens rotate and expire (14 days by default) | no stated IP retention period |
| Audit log (actor, action, IP address, time) | `audit_logs` | append-only by database trigger; readable by administrators | append-only design conflicts with erasure requests; a policy is needed |
| Waste reports and incident reports: photo, description, place | reports and incidents tables, image storage | photos are re-encoded and stripped of EXIF and GPS data; reporter identity and private addresses are not shown on maps | no stated retention period for reports; photos may show people or vehicle plates |
| Collector vehicle positions | `vehicle_location_events` | source and age labelled; simulator separated; purge command with default 90-day retention (`purge-location-events`, to be scheduled) | **location of workers is personal data**: a deployment needs a lawful basis, notice and agreement with the workforce |
| Help-assistant conversations | support tables | stay with the creator; shared with staff only if the user ticks the option; purge command with default 90 days (`purge-assistant-conversations`) | purge must be scheduled by the operator (the platform has no scheduler) |
| Rewards ledger, marketplace listings and requests | rewards and marketplace tables | append-only ledger; staff see owner names only where needed to hand a reward over | none beyond the above |

**OWNER:** a real deployment in India would need a privacy notice and a lawful-basis and retention decision under the
applicable law (the Digital Personal Data Protection Act, 2023, and its rules). That analysis has not been done here
and is not claimed.

## 4. AI-specific statements
* The classifier is a candidate and **inactive**; with no active model the API answers 503 `no_active_model` and the UI says so.
* It predicts only six material classes from the TrashNet taxonomy; it does not identify objects, brands or people.
* Its accuracy outside its training distribution was measured at 0.454 (RealWaste) against 0.867 on its own test split.
* Predictions are suggestions; low-confidence or unfamiliar images are routed to a human reviewer, who can correct
  them. A deployment should monitor the review and correction rate.
* Training data contain no people by design; inference photographs may. Photos are not used for training without a
  separate, consented process, which does not exist yet.
* The help assistant is retrieval-only: it generates no text and sends nothing to a third party.
* No emission or energy saving is claimed because no sourced coefficient exists.

## 5. Security and safety limits to state in a paper
* The security review is a self-review with automated tools; there has been no independent penetration test.
* Two-step verification is mandatory only for administrators and managers in production.
* The system has never been deployed; backup and restore were drilled locally only.
* Maps, tracking, e-mail and road routing were verified with simulators, mocks or local catchers, not live services.

## 6. Conflicts of interest, funding and authorship
The repository records no funding or institutional affiliation. **OWNER:** state them. Software was produced with
heavy assistance from AI coding agents (the commit history and `docs/project-completion/` show this); journals and
conferences have disclosure rules for AI assistance, so describe it as the venue requires.
