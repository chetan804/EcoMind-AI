# Known limitations (honest inventory)

Nothing in this list is hidden elsewhere in the product: the UI labels simulated
data, and this page is the complete list of what is **not** finished. Status
taxonomy: **implemented** · **simulated** (labelled) · **integration-ready**
(adapter exists, external provider needed) · **future**.

## Integration-ready (implemented adapter, needs an external provider)

| Capability | What exists | What's needed |
| --- | --- | --- |
| Real road geometry | OSRM client adapter, estimated-geometry fallback fully labelled | A deployed OSRM endpoint (`ECOMIND_OSRM_BASE_URL`) |
| LLM classification | Provider abstraction (OpenAI/Anthropic/Google) + deterministic baseline labelled SIMULATED | Provider API key |
| Email delivery | Password-reset / invitation token generation | SMTP or email API wiring |
| S3-compatible object storage | Storage abstraction, local backend implemented | S3 credentials/endpoint in the adapter |
| Live vehicle GPS | Position model + ingestion path; positions can be simulator-fed (labelled SIM GPS) | Fleet telematics integration |

## Deliberately simplified (documented decisions)

- **In-process rate limiting** — correct for single/low-replica deployments; a shared
  limiter is needed before horizontally scaling many replicas (ADR-0008).
- **Embedded job worker** — one process serves web + jobs by default for operational
  simplicity; split deployments are supported by config (ADR-0003).
- **HashRouter on the frontend** — zero server-rewrite requirements; deep links use
  `#/paths` (ADR-0007). Browser-history routing is a config swap if desired.
- **Alert engine is threshold-based** — no anomaly detection/ML on telemetry yet.

## Not yet implemented (future)

- WebSocket live push (UI polls via TanStack Query refetch intervals today)
- Native mobile apps (the field UI is a mobile-first web app)
- Offline mode / queue-from-device for the field app
- Multi-language UI (backend locale field exists; i18n strings not wired)
- Email/push notification channels (in-app notifications implemented)
- Route time-window constraints and driver shifts (capacity VRP today; time windows
  are modelled in the optimizer interface but not exposed in the UI)
- Billing/subscription management
- Formal SOC2/ISO audit artifacts (controls documented in SECURITY.md)
- Per-subject GDPR export endpoint (operator runbook covers it via CSV exports)

## Data honesty commitments

- AI inference without a configured provider is **always** labelled `is_simulated`
  and routed for human review when confidence is low. No fabricated confidence.
- Route distance/duration from the straight-line fallback is flagged
  `geometry_is_estimated=true` with the road factor recorded.
- Avoided emissions are stored as a separate modeled scope and never merged into
  net emissions. No carbon credits exist in the product.
- Empty organizations render empty states — dashboards never invent trend lines.
- The demo dataset is fully synthetic, flagged at the row level, and badged in the UI.
