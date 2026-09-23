# ADR-0005: Separate stop-sequencing (OR-Tools) from road geometry (OSRM)

**Status:** Accepted · **Date:** 2026-09

## Context

"Route optimization" conflates two different problems: deciding the *order* of
stops across vehicles under capacity (a combinatorial problem) and knowing the
*road distances/times/polylines* between them (a data problem). Bundling them —
e.g. calling a routing SaaS for everything — couples the product to one vendor and
hides solver provenance.

## Decision

Two layers with an explicit contract:

1. **Sequencing**: Google OR-Tools capacitated VRP. Multiple vehicles, capacities,
   fill-weighted demand from smart bins, depot start/end. Solver, status, solve
   time and any unassigned stops are stored on the route row (provenance).
2. **Geometry**: an OSRM adapter fetches real polylines + distances when
   `ECOMIND_OSRM_BASE_URL` is set. Without it, haversine × configurable road factor
   (default 1.3) produces an **estimate**, and the route is flagged
   `geometry_is_estimated=true` — visible in the API and badged in the UI.

## Rationale

- OR-Tools is open-source, industrial-grade and runs in-process — no vendor lock,
  no per-solve cost.
- OSRM is self-hostable and interchangeable with any compatible endpoint.
- The fallback keeps the product fully usable offline from third parties while
  being honest about precision — an estimate labelled as an estimate.

## Consequences

- Distances shown with estimated geometry are planning aids, not dispatch truth;
  the label travels with the data so downstream consumers can't miss it.
- Time-window constraints exist in the optimizer interface but are not yet exposed
  in the wizard (roadmap).
