# Known limitations

Everything below is a real, current limitation as of 2026-10-21 (branch `arena/cb4875bc-ecomind-ai`).
Nothing here is hidden elsewhere: statuses in `IMPLEMENTATION_STATUS.md` agree with this list.

## Machine learning
- **Classifier accuracy outside its training domain is low:** 0.867 on the TrashNet test split, 0.454 on
  real facility photos (RealWaste). No model is activated by default. See `docs/ml/`.
- Frozen backbone with a linear head; no fine-tuning (no GPU or deep-learning framework available here).
- Six material classes only. Organic, textile, e-waste, battery and medical waste are unsupported and go to
  review. Object or product identification is a different task and is not attempted.
- RealWaste (CC BY-NC-SA 4.0) and TrashBox (no licence) are not used for any released model (RealWaste only
  evaluates it, and any model trained on it may exist only as a labelled, inactive research artefact).
  **TACO was audited and no image qualifies:** its annotation file records no licence for 715 images, a bare
  "CC" for 319 and ODbL for 466, so none is provably CC BY / BY-SA / CC0 (`docs/ml/dataset-research/TACO_LICENCE_AUDIT.md`).
  Images can be admitted only after the owner runs the source-licence check and import scripts; the label
  conversion from TACO's 60 object categories to the six material classes is not defined yet. The classifier
  therefore still rests on TrashNet alone.
- Forecasting: the platform series starts empty; the two public series are reference data. Holt-Winters
  beat the baseline on two of four usable series. Anomaly detection has no labels, so no precision/recall.

## Product
- **Marketplace** (reference 08) is a matching board only: no price, payment, delivery, photos, chat, expiry, partial fulfilment or link to recovery records. Its notifications use the `system` category. **Smart bins and telemetry** (17, 19):
  excluded by product decision; no sensor integration.
- **Zones** have no boundary geometry (no verified boundary data), so no polygon or coverage figure is drawn. Collection tasks are not linked to zones.
- Route plans are ordered by straight-line distance and store no ETA. A road route (geometry, distance, duration, no live traffic) is fetched on demand only when a routing provider is enabled (`ROUTING_PROVIDER`: Google Routes with a server key, or an OSRM server the operator runs); it is not stored and the order is not re-optimised for roads. Both providers are tested with mocked transports only.
- Rewards have no redemption. Impact is reported as recovered weight; no emission coefficients are used.
- No e-mail verification and no password reset. No notification delivery beyond in-app.

## Maps and tracking (details: `docs/maps/OFFLINE_MAPS.md`, `ROUTING_PROVIDERS.md`, `GOOGLE_MAPS_INTEGRATION.md`)
- **The default offline map has only been rendered with synthetic tiles.** The basemap needs an owner-prepared PMTiles file from OpenStreetMap data (`scripts/maps/prepare_offline_maps.py tiles`, needs the `pmtiles` CLI and network); without it the screens draw markers and routes on a plain background and say "Base map not installed". How a real OSM region looks with this style, labels in non-Latin scripts (only Latin glyph ranges are shipped) and city-scale performance are unverified. It is an original OSM-based style, not a copy of Google Maps. No geocoding or turn-by-turn navigation.
- OSM data is a snapshot that the owner must refresh; ODbL attribution is shown on the map.
- **The optional Google integration is not verified live.** No key was available and the build sandbox cannot reach Google. Maps, advanced markers, clustering, the Routes API call and the CSP allowances are tested only with a fake `google.maps` and a mocked HTTP transport. The screenshots in `docs/ui/evidence/maps/` therefore show the labelled fallback, not Google tiles.
- **No real GPS source is connected.** The only real producer is the "Share my position" button of the collector's task dialog (browser geolocation, only while the tab is open, at most one report per 15 s, no background tracking, no native mobile app). Hardware trackers would post as the assigned collector's account: there are no per-device credentials or tokens (`gps_device` is accepted from a `fleet:track` user only).
- Positions update by polling every 15 s (backing off to 120 s); there is no SSE or WebSocket.
- Retention is a manual or cron job (`purge-location-events`); the platform has no scheduler.
- The simulator exists for demonstrations (managers only, off by default in production); simulated positions are always labelled and kept apart, and they follow straight lines unless provider geometry is supplied.
- Not mapped, because the data does not exist: zone boundaries, heatmaps, marketplace listing location, passport movement, geographic analytics.
- CSP omits `'unsafe-eval'` for Maps; if live testing shows it is needed, the policy must be amended.
- The local e2e suite stays within the 10 registrations per IP per hour limit (about 8 are used); adding specs that register users needs a larger budget or seeded accounts.

## Security (details: `docs/security/security-review.md`)
- MFA is TOTP only and not forced for any role; rotating `SECRET_KEY` invalidates stored MFA secrets.
- Per-address limits need trusted-proxy configuration in production.
- Registration reveals whether an e-mail exists (409). Password check is a small denylist.
- No antivirus scan on uploads; no automatic purge of orphaned uploads.
- CSP `connect-src` must be narrowed per deployment; nginx config untested locally.
- Backend dependencies use ranges (no lock file); no scheduled dependency audit.
- Incident photos need `waste_reports:create`; managers hold `users:read` (design choices to confirm).

## Engineering and quality
- Docker was unavailable in the build sandbox: Compose, images and the nginx file are validated only by CI.
- Light-theme contrast has not been audited; `ToastProvider` is not mounted.
- Visual similarity to the reference images is low (SSIM about 0.26 to 0.58 across screens); the references
  are small blurry composites, and **no fidelity claim is made**.
- Users search and audit filters query on each keystroke. Some IntegrityError race paths are untested.
- `seed_demo.py` has not been tested end to end in CI. `Settings.environment` is `local|test|production`.
- GitHub's `ubuntu-latest` label began migrating to Ubuntu 26 on 2026-10-19; CI has not been pinned.
- GitGuardian reports one false positive (a test credential in `test_administration.py`); it remains in history.
