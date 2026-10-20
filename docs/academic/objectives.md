# Problem statement and objectives

## Problem
Municipal waste operations commonly rely on separate spreadsheets for citizen reports, collection rounds,
vehicles and facility records. Material is mis-sorted, tasks are planned without volume estimates, and the
journey of recovered material cannot be traced. Machine-learning demos for waste sorting are widely
published, but they are rarely connected to the operational workflow, and they seldom report how they behave
outside their benchmark.

## Objectives and their status

| # | Objective | Status in this repository |
|---|---|---|
| O1 | Let residents report waste with a validated photo and track the report | Done (waste-reports module, upload validation, review) |
| O2 | Classify material from a photo, with calibrated confidence and an abstention path | Done as a candidate model; accuracy on real facility photos is low (see results) and no model is activated by default |
| O3 | Turn verified reports into collection tasks with a controlled lifecycle, fleet assignment and recorded weight | Done (collection, fleet; lifecycle enforced and tested) |
| O4 | Plan a deterministic visiting order for a vehicle | Done (straight-line ordering, no travel-time estimate) |
| O5 | Forecast collected volume and flag suspected anomalies, with baselines and provenance | Done on one platform series (empty until real data accrues) and public reference series |
| O6 | Trace recovered material through facilities | Done (recovery records, hash-chained passports) |
| O7 | Reward verified participation and report impact with sourced formulas only | Done (points rule documented; no redemption; no environmental coefficients invented) |
| O8 | Provide role-based access, MFA, audit and administration | Done (36 permissions, five roles, TOTP, audit log) |
| O9 | Provide an interface for every designed screen | 19 of 22 reference screens built; marketplace has no backend ("Soon"); two smart-bin/telemetry references are excluded by product decision |
| O10 | Evaluate honestly | Done: held-out and cross-dataset evaluation, calibration, per-class failure analysis, mutation checks of the tests |

## Scope boundaries
- Out of scope by decision: IoT sensor integration, a circular-surplus marketplace backend, map boundaries
  for zones (no verified map data), payments, and any native mobile app.
- The platform does not claim a real-world accuracy, real emission savings or live data. Illustrative or
  public reference data is labelled as such wherever it appears.
