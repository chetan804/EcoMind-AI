# Viva outline

## Five-minute story
1. **Problem:** waste operations are fragmented; ML demos are rarely tied to the workflow or tested outside
   their benchmark.
2. **Solution:** one platform from citizen report to verified recovery, with an honest classifier.
3. **Design:** modular monolith, PostgreSQL as the only authority, RBAC, audit, MFA, isolated ML package.
4. **Evidence:** held-out accuracy 0.867, but only 0.454 on real facility photos: I report both, and the
   system abstains and asks for review instead of pretending.
5. **Completeness:** 19 backend modules, 19 of 22 reference screens, nine migrations, end-to-end tests.
6. **Limits:** no marketplace, no sensors, no map geometry, no redemption, straight-line routes.

## Demonstration order (about 8 minutes)
Sign in as citizen and submit a report with a photo → as manager open the review queue, verify, create a task
→ assign collector and vehicle, build a route plan → as collector complete the task with a weight → show the
chain-of-custody passport and recovery record → show the reward ledger and the analytics page after refresh
→ show the audit log and the route-permission matrix.

## Likely questions and honest answers

**Why only 87% and why not 95/99%?** A frozen backbone with a linear head on 2,527 curated photos. I did not
promise a target; I measured, with intervals, and I reported that the figure falls to 45% on a different
dataset. Higher numbers would need more legitimate labelled field data and fine-tuning, which this
environment could not run.

**Why is the model not active by default?** Because no accuracy on real photos justifies it. An administrator
must activate a registered model deliberately; until then the API answers "no model" honestly.

**Why not train on RealWaste, which does much better on real photos?** Its licence is CC BY-NC-SA 4.0
(non-commercial, share-alike). Using it in a model that may be deployed is an owner decision; the experiment
is documented, nothing trained on it is released.

**What is calibration and why does it matter?** Confidence should match correctness. Temperature scaling on
the validation split gave ECE 0.031 in-domain; out of domain it was 0.263, which is exactly why the novelty
check and review queue exist.

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

**What would you do with more time?** Fine-tune with legitimate field data and licences; a marketplace
backend; sensor integration behind an adapter; travel-time routing; forced MFA for administrators; a
breached-password check and password reset; a full accessibility and light-theme contrast audit.

**What did testing find?** Real bugs, including CI-only failures (typing differences between numpy versions),
a missing nginx header inheritance, and CSP-incompatible library behaviour; all are in the commit history.

## Evidence map
`docs/ml/` (reports, cards, dataset research), `docs/security/` (review, matrix), `docs/database/` (ER
diagram, dictionary), `docs/ui/evidence/` (screenshots), `docs/project-completion/IMPLEMENTATION_STATUS.md`
(counts and CI).
