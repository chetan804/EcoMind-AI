# Abstract

EcoMind AI is a web platform that supports municipal solid-waste operations with recorded data
rather than guesswork. Residents report waste with a photo; the platform validates and re-encodes the image,
runs a material classifier **only when an administrator has activated an approved model** (and says so plainly
when none is active, which is the state of the shipped system), and queues uncertain results for human review.
Operators turn verified reports into collection tasks, assign vehicles and collectors, plan a visiting order,
record the collected weight, and follow the material through facilities with a hash-chained chain-of-custody
passport. Reward points, a staff-run redemption catalogue and impact figures are computed only from verified,
recorded quantities, and analytics are queries over the same database, so they are correct after a restart.

The system is a modular monolith: a React and TypeScript front end, a FastAPI back end with 22 modules and 168
operations over PostgreSQL 16 (SQLAlchemy and Alembic, 46 tables, 17 migrations), and an isolated `ml/` package
for training and evaluation. It includes deny-by-default role-based access control (5 roles, 48 permissions) with
TOTP two-step verification that is mandatory for administrators and managers in production, an audit log and
chain-of-custody records that the database itself refuses to alter, offline OpenStreetMap-based maps with an
optional road-routing adapter, a labelled vehicle-position simulator, a retrieval-only help assistant with a
support desk, weekly fill-volume forecasting against a naive baseline, a robust-score anomaly detector, and an
exact or heuristic route-ordering optimiser validated against a public routing dataset.

The classifier is a frozen EfficientNet-EdgeTPU feature extractor with a calibrated linear head. An earlier model
trained on TrashNet was withdrawn because the project has no written permission for those photographs. The current
research candidate is trained only on RealWaste (five material classes with a justified label mapping; one Australian
facility), behind a provenance gate that fails closed on missing licence evidence, prohibited data or split leakage.
On a group-aware held-out test split it reaches 0.895 accuracy (95% CI 0.855 to 0.931), 0.896 macro-F1 and 0.036
expected calibration error, and auto-accepts 82.9% of images at 93.5% accuracy. It nevertheless **fails** the project's
pre-declared acceptance test: only 79.7% of out-of-scope images (food, vegetation, textile, miscellaneous) are routed to
review against a required 90%, no Hyderabad field evaluation exists, and the dataset licence is contested (CC BY 4.0
on UCI, CC BY-NC-SA 4.0 on the authors' repository). The classifier is therefore shipped as an inactive, research-only
candidate, activation is refused by the API, and the platform makes no field-accuracy claim and does not identify
individual objects. A consented Hyderabad collection protocol is specified but not run. The software is verified by
787 backend, 386 frontend, 118 ML and 147 contract tests and a 61-test browser suite; it has not been deployed, and
real e-mail delivery, real map tiles, real GPS devices, human screen-reader review and load on target hardware remain
unverified (see `LIMITATIONS.md`).

**Keywords:** solid-waste management, image classification, calibration, selective classification, distribution
shift, time-series forecasting, anomaly detection, vehicle routing, chain of custody, role-based access control.
