# Product guide

## Who it's for

| Persona | What they need | Where they live in the app |
| --- | --- | --- |
| **Citizen** | Report waste in 30 seconds, see it resolved, feel participation | Community dashboard, report wizard, my reports, impact, schedule |
| **Collector / Driver** | One-handed execution of today's route | Field app (mobile-first) |
| **Field Supervisor** | Know what's happening right now on the ground | Command center, routes |
| **Operations Manager** | Triage reports, resolve complaints, keep collections on schedule | Ops: reports, complaints, collection, fleet, devices |
| **Sustainability Analyst** | Defensible tonnage, diversion and carbon numbers | Sustainability intelligence |
| **Org Admin** | Members, roles, settings, alert rules, audit | Administration |
| **Executive** | Is service getting better? | Executive overview |
| **Platform Admin** | Cross-org health | Platform overview API |

## Core journeys

### Citizen reports waste
1. Sign in (or register, optionally joining an open organization).
2. **Report waste** wizard: description + optional category guess + optional photo
   (validated server-side: MIME allow-list, size cap, checksum) → location via GPS or
   map tap → review & submit.
3. AI classification attaches with a confidence score; below-threshold results are
   routed to human review (visible to ops, never silently accepted).
4. The citizen tracks status; resolution awards sustainability points (+25) —
   recognition only, explicitly **not** a financial instrument.

### Operations triage
1. Command center shows the live picture: layered map (bins by fill %, reports,
   complaints, vehicles, routes, zones), open alerts, fleet status, KPI strip.
2. Reports inbox: filter by status / low AI confidence; triage → start → resolve,
   with resolution notes.
3. Complaints: SLA due dates, overdue badges, assignment, public comments vs internal
   notes, resolution summary required to close.

### Route generation & execution
1. Ops generates a route: zone, date, depot, vehicles, driver → OR-Tools solves the
   capacitated VRP; solver provenance stored; geometry from OSRM or labelled estimate.
2. Supervisor approves; driver starts it from the field app.
3. Driver works stops one by one: collected weight (kg), contamination flag, or skip
   with a reason. Progress rolls up to the command center in near-real-time.

### Sustainability accounting
1. Collection events with weights → waste treatments (measured).
2. Analyst runs recompute → carbon records with quality labels and factor provenance.
3. Dashboard: treatment mix, diversion rate, scopes 1/3, avoided (modeled, separate),
   full record ledger, factor library. 30/90/365-day windows. CSV exports for audits.

## Feature catalogue (implemented vs labelled)

| Feature | Status |
| --- | --- |
| Auth (JWT + rotating refresh, reset, invites), RBAC | Implemented |
| Org self-service onboarding, zones, units, members | Implemented |
| Citizen reporting + AI classification | Implemented; AI provider pluggable — heuristic baseline labelled SIMULATED |
| Complaint lifecycle + SLA + escalation + comments | Implemented |
| Collection points/schedules/events, weights | Implemented |
| Fleet registry + positions | Implemented; live GPS ingest is integration-ready (positions may be simulator-fed and are labelled) |
| Route optimization (OR-Tools CVRP) | Implemented |
| Road geometry (OSRM) | Integration-ready: adapter implemented, requires an OSRM endpoint; fallback labelled "estimated" |
| IoT registry, authenticated ingestion, alert rules, alerts | Implemented |
| Telemetry simulator | Implemented, explicitly labelled SIMULATED, off by default |
| Sustainability engine + factor library + recompute | Implemented |
| Analytics dashboards + CSV exports | Implemented |
| Notifications (in-app), rewards ledger, leaderboard | Implemented (email/push are roadmap) |
| Audit log | Implemented |
| Maps | Implemented (Leaflet + CARTO/OSM raster tiles) |

## Demo environment

The seeded `aurora-demo` organization demonstrates every surface with realistic,
internally-consistent data: 4 zones, 52 collection points, 6 vehicles, 14 simulated
smart-bin sensors with 5 days of telemetry, 38 waste reports (with simulated AI
inferences), 18 complaints with SLA states, ~30 days of collection events, 4 optimized
routes, alerts, notifications and a rewards ledger. Every simulated row is labelled at
the database level and badged in the UI.
