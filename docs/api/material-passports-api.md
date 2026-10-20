# Material passports and chain of custody API

Base path `/api/v1/material-passports`. Reading needs `passports:read`; writing needs `passports:manage` (facility operators, managers, administrators). Collectors and citizens have no access.

| Method and path | Purpose |
|---|---|
| `GET /material-passports` | List (`status`, `material_category_id`, `facility_id`, `q` = code fragment, `sort_by`, `order`) |
| `POST /material-passports` | Create a passport (`201`); the `created` custody event is written automatically |
| `GET /material-passports/{id}` | Passport with its ordered custody events |
| `GET /material-passports/by-code/{code}` | Same, by `MP-XXXXXXXXXX` code (case-insensitive) |
| `POST /material-passports/{id}/events` | Append a custody event (`201`) |
| `POST /material-passports/{id}/recovery` | Link a recovery record |
| `GET /material-passports/{id}/integrity` | Check the recorded chain |

## Custody state machine

```
created ─▶ collected | transferred | received
collected ─▶ transferred | received
transferred ─▶ transferred | received
received ─▶ transferred | processed
processed ─▶ verified            (needs a linked recovery record that is itself verified)
verified: final; the passport becomes `recovered`
```

Anything else is `409 invalid_custody_event`; a `recovered` or `retired` passport takes no events (`409 passport_closed`). `transferred` and `received` need `to_facility_id` (active facility); a transfer must change facility; while transferred the batch has no `current_facility_id` (in transit) until the receiving facility records `received`. `occurred_at` defaults to now, must carry a timezone, may not be in the future or earlier than the previous event (`422`). `processed` sets `in_processing`.

Linking a recovery record: it must exist, not be rejected, be for the same material category, and not be linked to another passport (`409`).

## Append-only guarantee

Custody events are never updated or deleted by the application, **and** migration 0007 installs a database trigger that rejects any `UPDATE` or `DELETE` on `custody_events` (including cascades from deleting a passport). The integrity endpoint verifies sequence continuity, the first event, allowed successors and time order. It is a consistency check on stored data, **not** a cryptographic proof or a blockchain; its `basis` field says so. A table owner can still disable the trigger deliberately; the integrity endpoint then reports the damage (covered by a test).

Audit events: `material_passport.created|collected|transferred|received|processed|verified|recovery_linked`.
