# Known limitations

Everything below is a real, current limitation as of 2026-10-21 (branch `arena/483a088d-ecomind-ai`).
Nothing here is hidden elsewhere: statuses in `IMPLEMENTATION_STATUS.md` agree with this list.

## Machine learning
- **Classifier accuracy outside its training domain is low:** 0.867 on the TrashNet test split, 0.454 on
  real facility photos (RealWaste). No model is activated by default. See `docs/ml/`.
- Frozen backbone with a linear head; no fine-tuning (no GPU or deep-learning framework available here).
- Six material classes only. Organic, textile, e-waste, battery and medical waste are unsupported and go to
  review. Object or product identification is a different task and is not attempted.
- RealWaste (CC BY-NC-SA 4.0) and TrashBox (no licence) are not used for any released model. TACO was not
  ingested (segmentation labels; images not reachable from the build environment).
- Forecasting: the platform series starts empty; the two public series are reference data. Holt-Winters
  beat the baseline on two of four usable series. Anomaly detection has no labels, so no precision/recall.

## Product
- **Marketplace** (reference 08) is a matching board only: no price, payment, delivery, photos, chat, expiry, partial fulfilment or link to recovery records. Its notifications use the `system` category. **Smart bins and telemetry** (17, 19):
  excluded by product decision; no sensor integration.
- **Zones** have no boundary geometry (no verified boundary data), so no polygon or coverage figure is drawn. Collection tasks are not linked to zones.
- Route plans are ordered by straight-line distance and store no ETA. A road route (geometry, distance, duration, no live traffic) is fetched on demand from the Google Routes API only when `GOOGLE_MAPS_SERVER_API_KEY` is set; it is not stored and the order is not re-optimised for roads.
- Rewards have no redemption. Impact is reported as recovered weight; no emission coefficients are used.
- No e-mail verification and no password reset. No notification delivery beyond in-app.

## Maps and tracking (details: `docs/maps/GOOGLE_MAPS_INTEGRATION.md`)
- **Google integration is not verified live.** No key was available and the build sandbox cannot reach Google. Maps, advanced markers, clustering, the Routes API call and the CSP allowances are tested only with a fake `google.maps` and a mocked HTTP transport. The screenshots in `docs/ui/evidence/maps/` therefore show the labelled fallback, not Google tiles.
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
