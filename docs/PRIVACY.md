# Privacy documentation

## Data categories

| Category | Examples | Stored | Visibility |
| --- | --- | --- | --- |
| Account | email, full name, phone (optional), locale | `users` | self + org admins (members list) |
| Citizen reports | description, photo, coordinates, address | `waste_reports`, `media_assets` | org ops roles; reporter |
| Complaints | subject, description, comments | `complaints`, complaint comments | org ops roles; reporter |
| Field activity | stop weights, notes, completion times | route stops, collection events | org ops roles |
| Telemetry | fill %, temperature, battery per device | `telemetry_readings` | org ops roles |
| Rewards | points ledger with reasons | `reward_ledger` | self + org (leaderboard names) |
| Audit | actor, action, before/after, IP-derived label | `audit_events` | `audit:read` roles |
| Tokens | refresh token hashes, reset token hashes | auth tables | never exposed |

## Principles

1. **Tenant boundary = privacy boundary.** Cross-org access is technically prevented
   (see SECURITY.md) and tested as release-blocking. One operator cannot see another
   operator's citizens or data.
2. **Anonymous reporting supported.** Organizations can enable anonymous reports;
   reporter identity is then not attached to the report.
3. **Purpose-limited points.** Sustainability points are engagement recognition only —
   they are not currency, not transferable, and carry no monetary value by design.
4. **Precise location, minimal exposure.** Coordinates are collected to route work
   (report triage, collection), shown only to the organization's own staff. They are
   never sold, shared, or used for advertising (no third-party analytics in the app).
5. **AI processes photos/text only for classification.** Provider-agnostic pipeline;
   with no provider configured, a local deterministic classifier runs (no data leaves
   the deployment). Enabling an external provider is an explicit deployment choice.

## Retention & deletion (operator-configurable)

- The platform implements hard deletes for organizations (FK cascade via the demo
  reset path, reusable for offboarding) and per-row deletion through the API where
  permissions allow.
- Uploaded media are content-addressed on disk/object storage and removed with their
   owning rows.
- Recommended retention baselines for operators: telemetry 12–24 months (aggregate
  summaries keep trends without raw rows), audit 12+ months (compliance), JWT refresh
  rows until rotated/expired (automatic).

## Data subject requests

- **Access/export**: citizens can view their reports; org admins can export
  collections/reports CSVs (`/analytics/export/*`); a per-subject export is a
  documented operator runbook step (OPERATIONS.md).
- **Deletion**: report/complaint deletion cascades timelines, comments and linked
  media; account deletion removes memberships and anonymizes reporter references
  where the schema stores ids (FK SET NULL).

## What the platform deliberately does NOT do

- No third-party trackers, ad pixels, or session recorders.
- No selling or cross-tenant "insights" from tenant data.
- No biometric processing.
- No tradable carbon instruments derived from citizen behavior.
