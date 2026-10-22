# Known limitations

Everything below is a real, current limitation as of 2026-10-22 (code at `main` `625241e`, migration head `0017`).
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
- **Marketplace** (reference 08) is a matching board only: no price, payment, delivery, chat, partial fulfilment or link to recovery records. Listings expire (default 30 days, renewable), closing records an outcome and up to four photos are re-encoded with metadata removed, but expiry runs only when the `expire-marketplace-listings` job is scheduled by the operator. Its notifications use the `system` category. **Smart bins and telemetry** (17, 19):
  excluded by product decision; no sensor integration.
- **Zones** have no boundary geometry (no verified boundary data), so no polygon or coverage figure is drawn. Collection tasks are not linked to zones.
- Route plans are ordered by straight-line distance and store no ETA. A road route (geometry, distance, duration, no live traffic) is fetched on demand only when a routing provider is enabled (`ROUTING_PROVIDER`: Google Routes with a server key, or an OSRM server the operator runs); it is not stored and the order is not re-optimised for roads. Both providers are tested with mocked transports only.
- **Rewards** redemption is a hand-over workflow: staff enter the catalogue (no partner integration, stock feed, payment or delivery), a citizen's points are spent against a claim code, and staff fulfil or cancel at the counter. Item stock and the per-citizen limit are enforced, but nothing is ever shipped or paid by the platform. Impact is reported as recovered weight; no emission coefficients are used.
- Password reset and e-mail verification exist, but **no e-mail has been delivered through a real SMTP server** (only the console backend and mocked transport were exercised). Verification is not required by default (`EMAIL_VERIFICATION_REQUIRED`). No notification delivery beyond in-app and these account e-mails.

## Help assistant and support desk (details: `docs/ml/support-assistant.md`, ADR-0003)
- The assistant is **retrieval only**: it quotes articles and reads the person's own records. It does not generate text and it does not understand paraphrases well: on an author-written held-out set about 45% of in-scope questions got no direct answer (it suggested the right article for 13 of those 18). The held-out set was reused after a rule change, so its numbers are optimistic; no real-user questions have been measured.
- The 31 starter articles were written from the code and screens of this repository and checked against them, but they describe platform defaults; an operator must review them for their own policies. They are English only.
- A generative model was not added: no provider, key or data-processing decision exists (ADR-0003). Adding one is an owner decision.
- Requesters hear about replies through in-app notifications only (no e-mail); the desk has no SLA timers, categories, attachments or satisfaction survey.
- MFA is required for administrators and managers only when `ENVIRONMENT=production` (override with `MFA_REQUIRED_ROLES`); in local and test stacks it stays optional so they work without an authenticator. Rolling it out to existing privileged accounts means they are held to the Security page until they enrol; there is no grace period.

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
- The e2e suite registers 9 accounts from one address per run (more on a Playwright retry), which exceeds the production limit of 10 per address per hour once retries happen (this is what failed CI on `a97911d` and `b9704d0`). The limit is now the setting `REGISTRATION_LIMIT_PER_IP_PER_HOUR` (default 10); only the throw-away CI stack raises it. A local run needs a fresh hour or the same override.

## Security (details: `docs/security/security-review.md`)
- MFA is TOTP only (required for administrators and managers in production); rotating `SECRET_KEY` invalidates stored MFA secrets.
- Per-address limits need trusted-proxy configuration in production.
- Registration reveals whether an e-mail exists (409). Password check is a small denylist.
- No antivirus scan on uploads; no automatic purge of orphaned uploads.
- CSP `connect-src` must be narrowed per deployment; nginx config untested locally.
- Backend and ML dependencies are pinned by hash-locked files, and Dependabot plus the `security.yml` audit run on a schedule, but base images cannot be pinned by digest from the build sandbox and Dependabot cannot rewrite the `.lock` files (regenerate them with `scripts/dependencies/lock_backend.sh`).
- Incident photos need `waste_reports:create`; managers hold `users:read` (design choices to confirm).

## Engineering and quality
- Docker was unavailable in the build sandbox: Compose, images and the nginx file are validated only by CI.
- **Accessibility is partly automated.** Token contrast is checked by `scripts/quality/check_contrast.py` (in CI) and axe-core runs on 22 routes in both themes. Automated tools catch only a minority of WCAG issues (commonly estimated at around a third, which is a general industry estimate and not a measurement of this product). An automated keyboard-only browser suite exists (`tests/e2e/specs/keyboard.spec.ts`, 7 tests: skip link, visible focus indicators and no focus trap, account menu, page-search dialog, phone navigation drawer, keyboard navigation and sign-out; passed locally) but a person's keyboard review and any screen-reader review (NVDA, VoiceOver, TalkBack) have **not been done** (a blank test form is in [ACCESSIBILITY_MANUAL_CHECKLIST.md](../testing/ACCESSIBILITY_MANUAL_CHECKLIST.md)). The e2e database holds little data, so contrast of populated tables, charts, status chips and overlay gradients is unscanned; the landing and public pages and the Google Maps view are outside the axe run; the offline map canvas is excluded.
- Visual similarity to the reference images is low (SSIM about 0.26 to 0.58 across screens); the references
  are small blurry composites, and **no fidelity claim is made**.
- Users search and audit filters query on each keystroke. Some IntegrityError race paths are untested.
- `seed_demo.py` has not been tested end to end in CI. `Settings.environment` is `local|test|production`.
- Workflows pin `ubuntu-24.04` and every action by commit SHA; the two runner pins need a manual bump when a runner image is retired.
- GitGuardian reports one false positive (a test credential in `test_administration.py`); it remains in history.
- **Load and capacity are not established.** `scripts/perf/load_test.py` ran in the build sandbox (2 vCPU, one API worker, database and web server on the same machine, tiny demo data): about 125–130 requests per second saturation, 0 errors at 10 and 50 users, p95 123 ms and 639 ms. Those numbers describe that machine only; no target was set and there is no test on target hardware or with realistic data volumes. See `docs/operations/load-testing.md`.

## Publication and release
- The repository's `LICENSE` is "All rights reserved; no license is granted". The code is not open source until the owner chooses a licence; a paper must state this honestly.
- No user study, pilot or field data exist; the ethics and data-licence statement (`docs/academic/ethics-and-data-statement.md`) is a draft and the gaps to a research paper are in `docs/academic/PAPER_READINESS.md`.
- The related-work survey (`docs/academic/literature-survey.md`) is selective, not a protocol-based search.
