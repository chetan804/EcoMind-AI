# Roadmap

Priorities reflect the product goal: trustworthy operations for real waste
organizations. Items are sequenced by user value vs. effort.

## Now (next 1–2 milestones)

1. **Email delivery wiring** — password reset, invitations, complaint updates via
   SMTP/provider adapter (tokens already implemented).
2. **WebSocket live push** — command center and field updates without polling;
   keep the query cache as the fallback transport.
3. **Route time windows & driver shifts** — expose the optimizer's window support in
   the generation wizard; shift calendars for collectors.
4. **Redis-backed rate limiter + shared job queue lock** — unlock horizontal replicas
   (replaces the in-process limiter; ADR-0008 revisit).
5. **Per-subject data export endpoint** — one-click GDPR-style export (JSON+CSV)
   for account holders.

## Next (3–6 months)

6. **Field offline mode** — service-worker cache + queued stop updates with
   conflict resolution on reconnect.
7. **Native mobile shells** — wrap the field/citizen web experience (Capacitor or
   similar) with camera/GPS native APIs.
8. **Weighbridge / scale integrations** — ingest real vehicle weights against
   collection events (treatment data quality: measured vs estimated).
9. **Anomaly detection on telemetry** — statistical baselines per device; alert on
   deviation beyond thresholds (fills the gap between threshold alerts and reality).
10. **Sustainability report packs** — scheduled PDF/CSV report generation with
    methodology appendix for council/audit use.
11. **i18n** — extract strings, ship 2–3 locales (backend locale already stored).

## Later (6+ months)

12. **Marketplace for integrations** — telematics, ERPs, city open-data portals.
13. **Transfer-station / MRF operations** — intake weighing, contamination sampling,
    downstream treatment tracking (completes the treatment-quality chain).
14. **Predictive collection planning** — fill-level forecasting to schedule
    collections ahead of overflow (needs ~90 days of telemetry history).
15. **Billing & plans** — subscription tiers per organization.
16. **Compliance artifacts** — SOC 2 Type I/II readiness evidence automation.

## Non-goals (deliberate)

- **Tradable carbon instruments** — the platform reports avoided emissions as a
  modeled counterfactual only. Creating offset-like products invites greenwashing
  and regulatory exposure; it's a product non-goal (ADR-0006).
- **Cryptocurrency/token mechanics** for citizen rewards — points are recognition
  only, by design.
- **Cross-tenant data pooling** for "benchmarks" without explicit, revocable,
  per-organization opt-in.
