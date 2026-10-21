# Abstract

EcoMind AI is a web platform that supports municipal solid-waste operations with data rather than
guesswork. Residents report waste with a photo; the platform checks the image, runs a material classifier
when an activated model exists (and says so plainly when none does), and queues uncertain results for human
review. Operators turn verified reports into collection tasks, assign vehicles and collectors, plan a visiting
order, record the collected weight, and follow the material through facilities with a hash-chained
chain-of-custody passport. Reward points and impact figures are computed only from verified, recorded
quantities, and analytics are queries over the same database, so they are correct after a restart.

The system is a modular monolith: a React and TypeScript front end, a FastAPI back end with 22 modules over
PostgreSQL (SQLAlchemy and Alembic, sixteen migrations), and an isolated `ml/` package for training and
evaluation. It includes role-based access control with optional TOTP multi-factor authentication, an audit log,
weekly fill-volume forecasting with a naive baseline, a robust-score anomaly detector, and an exact or
heuristic route-ordering optimiser validated against a public routing dataset.

The classifier is a frozen EfficientNet-EdgeTPU feature extractor with a calibrated linear head trained on
TrashNet (six material classes). On its own held-out test split it reaches 0.867 accuracy (95% CI
0.813 to 0.912) with 0.031 expected calibration error. On real facility photographs from a second dataset
(RealWaste) the same model reaches only 0.454 accuracy, which is why it is shipped as a non-default
candidate and why low-confidence and out-of-scope inputs are sent to review. This gap between a curated
benchmark and field-like images is a central, honestly reported finding.

**Keywords:** solid-waste management, image classification, calibration, transfer learning, time-series
forecasting, anomaly detection, vehicle routing, chain of custody, role-based access control.
