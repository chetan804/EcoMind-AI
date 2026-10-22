# Viva outline

## Five-minute story
1. **Problem:** waste operations are fragmented; ML demos are rarely tied to the workflow or tested outside
   their benchmark.
2. **Solution:** one platform from citizen report to verified recovery, with an honest classifier.
3. **Design:** modular monolith, PostgreSQL as the only authority, RBAC, audit, MFA, isolated ML package.
4. **Evidence:** held-out accuracy 0.895 (macro-F1 0.896) on one Australian facility's photographs, but the
   pre-declared acceptance test failed (out-of-scope routing 79.7% vs 90%) and there is no Hyderabad evidence: I report
   both, and the system abstains and asks for review instead of pretending.
5. **Completeness:** 22 backend modules, 20 of 22 reference screens (the other two are excluded or ambiguous), seventeen migrations, 168 API operations, and 788 backend, 386 frontend, 118 ML and (last run 2026-10-21) 61 end-to-end tests passing.
6. **Limits:** no approved classifier, never deployed, marketplace without payment, no sensors, no zone boundaries, straight-line routes by default, tracking verified only with a simulator, maps only with synthetic tiles, no user study, no human accessibility review.

## Demonstration order (about 8 minutes)
Sign in as citizen and submit a report with a photo → as manager open the review queue, verify, create a task
→ assign collector and vehicle, build a route plan → as collector complete the task with a weight → show the
chain-of-custody passport and recovery record → show the reward ledger and the analytics page after refresh
→ show a vehicle on the map (simulator, clearly labelled) → show the audit log and the route-permission matrix.

## Likely questions and honest answers

**Why only about 90% and why not 95/99%?** A frozen backbone with a linear head on 3,092 labelled photographs from one
facility. I did not promise a target; I set acceptance criteria before training, measured with intervals, and reported
the one that failed. Higher numbers would need more legitimate labelled field data and fine-tuning, which this
environment could not run. The score is not a Hyderabad accuracy.

**Why is the model not active by default?** Because no accuracy on real photos justifies it. An administrator
must activate a registered model deliberately; until then the API answers "no model" honestly.

**Why not TrashNet, which everyone uses?** The project has no written permission for its photographs, so it is excluded
and a hash denylist stops it re-entering. **Is the RealWaste model releasable?** No: its licence is contested (UCI says
CC BY 4.0, the authors' GitHub says CC BY-NC-SA 4.0), so the model is research-only until the authors confirm in writing.

**What is calibration and why does it matter?** Confidence should match correctness. Temperature scaling on
the held-out split gave ECE 0.036 in-domain; I have no out-of-domain calibration figure for 2.0.0, which is why the
novelty check, the review queue and a field evaluation exist.

**Why a modular monolith?** One team, one database, transactional integrity across report, task, weight and
reward. Modules own their tables and communicate through services; extraction is possible later.

**How do you know authorization is complete?** A test lists every route, requires each to have a permission or
sit on an explicit allow-list, and a generated matrix documents who can call what. I also broke a rule on
purpose to confirm the test fails.

**How are anomalies validated?** They are not, in the sense of precision/recall: there are no labels. The UI
says "suspected anomaly" and the workflow records human outcomes (acknowledged, false positive), which can
become labels later.

**Is the forecast reliable?** It beats a naive baseline on two long series and not on two short noisy ones;
the API shows the baseline and refuses to forecast with under 26 weeks of data.

**What would you do with more time?** Fine-tune with legitimate field data and licences; sensor integration behind an adapter; travel-time routing on a self-hosted OSRM with real Hyderabad data; real e-mail and GPS pilots; MFA policy for collectors and operators; a breached-password check; a human accessibility review and a user study; account deletion and data export (not implemented).

**Is two-step verification mandatory?** For administrators and managers when `ENVIRONMENT=production` (they are blocked until they enrol); optional for other roles and in development. Enrolment is permanent per account until an administrator resets it.

**Does the marketplace take payments or photos?** No payment or delivery. A listing can carry up to four photos, each re-encoded with metadata removed.

**Can users redeem points?** Yes, against a catalogue that staff fill in; the platform ships no rewards and gives points no monetary value.

**Is the live tracking real?** The mechanism is real (append-only position events with source and age, stale positions labelled), but it was verified only with a clearly labelled simulator and emulated browser geolocation. No physical GPS device or phone was connected.

**Is the database tamper-proof?** The audit log, custody events, reward ledger, location events and task status history reject UPDATE and DELETE through triggers, and custody events are hash-chained. A database superuser can still drop the triggers or truncate the tables, so this is tamper-resistance against application bugs and ordinary roles, not against the database owner.

**What did testing find?** Real bugs, including CI-only failures (typing differences between numpy versions),
a missing nginx header inheritance, and CSP-incompatible library behaviour; all are in the commit history.

## Evidence map
`docs/ml/` (reports, cards, dataset research), `docs/security/` (review, matrix), `docs/database/` (ER
diagram, dictionary), `docs/ui/evidence/` (screenshots), `docs/project-completion/IMPLEMENTATION_STATUS.md`
(counts and CI).
