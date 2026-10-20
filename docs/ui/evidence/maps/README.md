# Map screen evidence (2026-10-21)

Real Chromium screenshots of the production-style frontend (Vite dev server, local PostgreSQL, local API) taken by
`tests/e2e/visual/capture-maps.mjs`, which seeds a clearly named **synthetic "Demo…" scenario** through the public API
(depot, zone, vehicles, collection tasks, a route plan, real-source test positions sent as the assigned collector, and simulator positions).

**These images show the no-key fallback, not Google tiles.** No Google key was available and the sandbox cannot reach Google, so
`VITE_GOOGLE_MAPS_API_KEY` was empty. Each map shows the labelled "Google Maps is not configured" notice and the same locations as a table with
status and recorded time. Read them as evidence that the fallback is honest and complete (LIVE GPS, SIMULATED and LOCATION UNAVAILABLE are distinct; the route
plan says straight lines are not roads), **not** as evidence that Google rendering works. That check is pending (`docs/maps/GOOGLE_MAPS_INTEGRATION.md`).

The "LIVE GPS" positions were posted by the capture script as a test collector moments before the screenshot; they are not a real vehicle.
Rows from earlier script runs also appear in the shared list.

Regenerate with a running stack: see the header of the script.
