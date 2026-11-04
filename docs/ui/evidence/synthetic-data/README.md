# Dashboard screenshots with the synthetic development dataset

Real Chromium screenshots (1440 x 900, dark theme) of the running application on 2026-11-04, signed in as the
demonstration accounts, with the `development` synthetic profile loaded (about 52 k generated rows; see
`docs/database/synthetic-data.md`). The data is generated: the manager dashboard shows the
"Demonstration data, not live" notice because the overview API reports `contains_demonstration_data`.

The collector account (`collector@example.org`) and facility operator account have no generated tasks of their own
(generated people cannot sign in), so their homes show the role layout, not a populated work list.
