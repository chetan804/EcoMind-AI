# Community incidents API

Base path `/api/v1/community-incidents`. Residents and field staff report problems (illegal dumping, overflowing bins, ...); triage staff acknowledge, assign and close them.

| Method and path | Permission | Purpose |
|---|---|---|
| `POST /community-incidents` | `incidents:create` | Report an incident (`201`) |
| `GET /community-incidents` | `incidents:read_own` or `incidents:triage` | List. Triage staff see everything; others see their own reports and the incidents assigned to them |
| `GET /community-incidents/summary` | `incidents:triage` | Totals by status and type, open and unassigned counts |
| `GET /community-incidents/{id}` | `incidents:read_own` or `incidents:triage` | One incident. Visible to its reporter, its assignee and triage staff; anyone else gets `404`, indistinguishable from a missing one. An assignee can read but not change it |
| `POST /community-incidents/{id}/assign` | `incidents:triage` | Assign to an active user holding `incidents:triage` or `collection:execute` |
| `POST /community-incidents/{id}/status` | `incidents:triage` | Move along the lifecycle |

**Roles.** Citizen: report and read own. Collector: may report (field staff see problems) but cannot list. Facility operator: neither. Manager and administrator: triage.

## Reporting

`incident_type` (`illegal_dumping`, `overflowing_bin`, `hazardous_waste`, `missed_collection`, `open_burning`, `other`), `title`, and a location: either `latitude` and `longitude` together, or `address_text`. `description` is optional. An optional `photo_media_asset_id` must be a file **the reporter uploaded** with `POST /api/v1/waste-reports/media` (otherwise `422`). Photos are read through the same media endpoint (`photo_content_path` in the response); the uploader needs `waste_reports:create`, so a collector cannot attach a photo.

## Lifecycle

```
open ─► acknowledged ─► in_progress ─► resolved   (final)
  │          │               │
  └──────────┴───────────────┴──────► dismissed  (final)
acknowledged ─► resolved is also allowed
```

* `open` is only a starting state; the request body accepts `acknowledged`, `in_progress`, `resolved`, `dismissed`.
* `resolved` and `dismissed` require `notes` (`422` otherwise) and are stored as `resolution_notes` with `resolved_at`.
* Any other move is `409 invalid_incident_transition`. Assigning a closed incident is `409`.
* The reporter receives an in-app notification on each change; the audit log records `community_incident.<status>` and assignment.

## List filters

`status`, `incident_type`, `assigned_to_id`, `unassigned=true` (triage only), `q` (title/description search), `sort_by`, `order`, `page`, `page_size`.

## Not implemented

No SLA timers, no duplicate merging, no public (anonymous) reporting and no automatic dispatch: incidents are not turned into collection tasks automatically.
