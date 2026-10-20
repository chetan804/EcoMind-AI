# Google Maps integration and vehicle tracking

> **Google is now optional.** The default map is the built-in offline OpenStreetMap map that needs no key
> (`docs/maps/OFFLINE_MAPS.md`). Google Maps is used only when `VITE_MAP_PROVIDER=google` or a browser key is
> set. Road routing is chosen with `ROUTING_PROVIDER=none|google|osrm` (`docs/maps/ROUTING_PROVIDERS.md`).
> Everything below describes the Google option.

Status at 2026-10-21: **implemented and tested with a mocked Google Maps and a mocked Routes transport.
Not verified against live Google services** (no key was available and the build sandbox cannot reach
Google). Every check that needs a key is listed under "Pending live verification" below.

## What uses Google, and what deliberately does not

| Need | Mechanism | Needs a key | Where |
|---|---|---|---|
| Interactive maps, markers, clusters, polylines | Maps JavaScript API (`AdvancedMarkerElement`, `Polyline`, `@googlemaps/markerclusterer`) | browser key | `frontend/src/features/maps` |
| Road geometry, distance and duration of a route plan | Routes API `computeRoutes` (REST) | server key | `backend/app/integrations/mapping/google_routes.py`, `GET /api/v1/route-planning/plans/{id}/road-route` |
| "Directions" link on facilities | plain `https://www.google.com/maps/dir/?api=1&destination=lat,lng` link | none (no API call) | facilities screen |
| Stop **ordering** | the platform's own optimiser (`route-order 1.0.0`, straight-line distances) | none | `route_planning` |
| Geocoding, Places, Route Optimization | **not integrated** (addresses are typed, coordinates are picked on the map) | n/a | |

Without a key the product works: the offline map is used (or, in a browser without WebGL, a labelled list of
the same locations), route plans show straight lines labelled as such, and nothing is requested from Google.

## Keys (placeholders only in `.env.example`; never commit a real key)

| Variable | Used by | Exposure | Restrict it by |
|---|---|---|---|
| `VITE_GOOGLE_MAPS_API_KEY` | browser bundle (Maps JavaScript API) | **public by design** (visible in the built JS) | HTTP referrer (your site origins) **and** API restriction to "Maps JavaScript API" |
| `VITE_GOOGLE_MAPS_MAP_ID` | browser | public | Cloud-based map ID; default `DEMO_MAP_ID` is only for development (advanced markers need a map ID) |
| `GOOGLE_MAPS_SERVER_API_KEY` | backend only (Routes API) | **secret**; never a `VITE_` variable, never in the bundle, sent only in the `X-Goog-Api-Key` header, never logged or returned | IP address of the backend host **and** API restriction to "Routes API" |
| `GOOGLE_ROUTES_TIMEOUT_SECONDS` | backend | | default 8 |

`VITE_*` values are compiled in at **build** time: set them when building the frontend image
(`compose.yaml` passes them as build args). Changing the browser key needs a rebuild.

## APIs to enable in Google Cloud

1. **Maps JavaScript API** (browser key).
2. **Routes API** (server key).
3. A billing account must be attached (Google requires it for both).

Create two separate keys so the browser key can be referrer-restricted and the server key IP-restricted.
Set budget alerts and, if wanted, daily quotas per API in the Cloud console.

## Charges (check the current pricing page; this document does not quote prices)

Pricing and free monthly allowances change: <https://developers.google.com/maps/billing-and-pricing/pricing>.
What the code does to keep usage low:

* **Maps JavaScript:** the script is injected only when a screen that has a map is rendered and a key is
  configured. Markers are diffed (unchanged markers are not recreated); the view is re-fitted only when
  the set of items changes, not on each position update.
* **Routes API:** one request per plan while the route has at most 12 points including depot start and end
  (10 intermediate waypoints); longer routes are split into consecutive chunks of at most 10 intermediates, so the
  request count is `ceil(legs / 11)` (the response reports `request_count`). Requests use
  `TRAFFIC_UNAWARE` and a field mask, which keeps them on the lowest Routes SKU tier at the time of
  writing (verify on the pricing page). The request is made when a plan is opened and again only when the user presses
  "Recompute road route" (the browser reuses the answer for 5 minutes when the same plan is reopened): it is not polled. Nothing from Google is stored in the database (the
  provider's terms limit caching; the code keeps nothing).
* Tracking polling talks only to this platform's own API, never to Google.

## What the user sees when Google is unavailable

| Situation | Behaviour |
|---|---|
| No `VITE_GOOGLE_MAPS_API_KEY` | "Map not available: Google Maps is not configured" plus a table of the same locations; no request to Google |
| Script blocked/offline | "Map could not be loaded" + retry button + the table |
| No answer in 12 s | "Map took too long to load" + retry + the table |
| Google rejects the key (`gm_authFailure`: bad key, wrong referrer, API not enabled, billing off) | "Google rejected the map key" (no retry: it needs an administrator) + the table |
| No `GOOGLE_MAPS_SERVER_API_KEY` | road-route endpoint answers `available: false, reason: not_configured`; the plan shows straight lines labelled "not roads" |
| Routes API quota/denied/timeout/network/bad response/no route | `available: false` with a specific `reason`; same labelled straight-line fallback; the endpoint itself answers 200 |

## Vehicle tracking architecture

```
collector's browser (Geolocation API, user presses "Share my position")  ─┐
GPS tracker posting through the assigned collector's account (fleet:track)─┼─▶ POST /tracking/vehicles/{id}/locations
manager importing a past track (fleet:manage, source "imported")          ─┘            │ validate, authorise, rate-limit, de-duplicate
                                                                                         ▼
simulator (fleet:simulate, own endpoint, own source)  ───────────────▶ vehicle_location_events (append-only, DB trigger blocks UPDATE)
                                                                                         │ latest-position query (indexed)
                                                                                         ▼
                                                              GET /tracking/vehicles, /collections/{id}, /route-plans/{id}
                                                                                         │ controlled polling, 15 s, backoff to 120 s
                                                                                         ▼
                                                                         fleet / command center / task / plan maps
```

Full API: `docs/api/tracking-api.md`. Module notes: `backend/app/modules/tracking/README.md`.

* **No vehicle has a coordinate of its own.** A vehicle appears on a map only if it has an event. A vehicle
  with none is listed as LOCATION UNAVAILABLE with no marker; a depot or the last task address is never
  used as a stand-in.
* **Freshness is derived at read time** from the source and the timestamp, never stored: real source
  ≤ 120 s → LIVE GPS, ≤ 900 s → DELAYED, older → STALE; imported → HISTORICAL; simulator → SIMULATED.
* **Out-of-order** events are stored (`quality=out_of_order`) and never become the latest position.
  Duplicates (same vehicle and timestamp, or same sequence) are acknowledged (200) without a new row.
* **Rate limit:** 30 events per vehicle per minute (429 with `Retry-After`).
* **Retention:** `python -m app.cli purge-location-events` removes events older than
  `TRACKING_RETENTION_DAYS` (default 90). Schedule it daily (cron or a systemd timer); the platform has no scheduler.
* **Simulator:** separate endpoints and permission (`fleet:simulate`, managers/administrators), `source =
  simulator` rejected on the real endpoint, rows kept in a separate group so they can never be a vehicle's
  real latest position, shown as SIMULATED with distinct markers and a "demonstration" label, deletable per vehicle
  (reset). Enabled outside production by default; `TRACKING_SIMULATOR_ENABLED` overrides.
  The simulator follows whatever path it is given: provider road geometry if available, otherwise straight lines
  between stops, and the screen says which.
* **Live GPS is not claimed.** The only real producer shipped is the browser sharing feature of the collection
  task dialog (verified end to end in the e2e test with Chromium's emulated geolocation). A hardware tracker or a
  native app would need to be built or configured and would authenticate as an ordinary user with `fleet:track`
  (there are no per-device credentials yet; see LIMITATIONS).

## Content Security Policy

`deployment/docker/nginx.conf` now allows the Google Maps hosts (script, image, connect, frame, font, style,
worker) following Google's CSP guide. `'unsafe-eval'` is **not** allowed, because the need for it is unverified.
If the live map fails to initialise with a CSP violation in the browser console, add it and record that
here; Google's guide lists it in its allowlist example. Run the CSP check (`docs/security/security-review.md`)
again with a key before relying on this.

## Where maps appear

| Screen | Map content |
|---|---|
| Dashboard (command center, `fleet:read`) | vehicles (layer toggle, simulated off by default) + facilities, clustering, freshness note |
| Fleet | same map with simulated layer on, plus a Position column per vehicle |
| Collection task (manager or assignee) | planned collection point, vehicle with status, recorded path linked to the task, "Share my position" for the assignee |
| Route plan | numbered stops, road route (provider) or labelled straight-line fallback, provider distance/duration, recorded/simulated path, stop completion from task status, recompute, simulator controls (`fleet:simulate`) |
| Facilities | map of the listed facilities, "Directions" links, location picker in the form |
| Locations and zones | located facilities of the selected zone; **no zone boundaries** (none exist) |
| Waste reports, incidents | location picker (click map, type, or press "Use my current location"), clustered map of the listed items, single-item map in the detail; labels carry status only, never reporter identity or free text |
| Marketplace, passports, executive analytics | **no map**: no genuine movement data (passports), no approximate-location field (marketplace), no geographic analytics API (analytics) |

## Pending live verification (needs keys; not done)

1. Maps render with a real browser key (referrer-restricted), including advanced markers, clustering and the
   detail panel; check the browser console for CSP violations (and whether `'unsafe-eval'` is needed).
2. Routes API: a real plan returns geometry, distance and duration; confirm chunked plans (> 10 stops) join correctly.
3. Key restriction behaviour (wrong referrer shows the "rejected key" message).
4. Quota/billing figures in your Cloud console after a day of use.
5. A real GPS source posting positions.

Automated tests use a fake `google.maps` and a mocked HTTP transport; no paid call is made by any test.
