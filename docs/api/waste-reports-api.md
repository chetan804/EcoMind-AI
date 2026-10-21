# Waste reports API

Base path `/api/v1/waste-reports`. All endpoints need `Authorization: Bearer <access token>` (see [auth-api.md](auth-api.md)). Errors use the standard envelope (`{"error": {"code", "message", "details", "request_id"}}`).

## Endpoints

| Method and path | Permission | Purpose |
|---|---|---|
| `POST /waste-reports` | `waste_reports:create` | Submit a report (optionally with photos). `201`, or `200` on an idempotent replay |
| `GET /waste-reports` | `waste_reports:read_own` **or** `read_all` | Paginated list, filter, search, sort |
| `GET /waste-reports/{id}` | `read_own` or `read_all` | One report |
| `POST /waste-reports/{id}/review` | `waste_reports:review` | Move a report through the review workflow |
| `POST /waste-reports/media` | `waste_reports:create` | Upload one photo (raw body). `201` |
| `GET /waste-reports/media/{id}/content` | `read_own` or `read_all` | Download a photo |

Who holds what: citizens `create` + `read_own`; collectors and facility operators `read_all`; managers and administrators also `review`. Collectors cannot submit reports.

## Visibility

A caller with `waste_reports:read_all` sees every report; everyone else sees only their own. A report (or photo) the caller may not see is answered with **404, not 403**, with the same message as a non-existent id, so ids cannot be probed. `mine=true` limits a staff user to their own reports.

## Submitting a report

```json
POST /api/v1/waste-reports
Idempotency-Key: 5f0c2c9e-7d3a-4a52-9d4e-1a2b3c4d5e6f      (optional, recommended)
{
  "title": "Overflowing bin near the market",     // 3-200 chars, trimmed
  "description": "...",                           // optional, <= 4000
  "address_text": "12 Lake Road",                 // optional, <= 500
  "latitude": "17.385044", "longitude": "78.486671",   // both or neither, WGS84
  "estimated_weight_kg": "42.5",                  // optional, 0..100000
  "media_ids": ["<id from POST /media>"]          // optional, <= 5, no duplicates
}
```

Unknown fields (for example `reporter_id` or `status`) are rejected with 422: the reporter is always the caller and a new report is always `submitted`. `estimated_weight_kg` is the reporter's estimate, not a measurement.

### Idempotency

Send `Idempotency-Key` (8-64 characters: letters, digits, `-`, `_`) so a retry after a network failure or double click cannot create a duplicate.

| Situation | Result |
|---|---|
| First request with a key | `201`, report created |
| Same key, same body, same user | `200` with `Idempotent-Replayed: true` and the original report; nothing is written |
| Same key, **different** body | `409 idempotency_key_reused` (never silently ignored) |
| Same key from another user | independent: keys are scoped per user |
| Two simultaneous requests with one key | exactly one report; one `201`, one `200` (database unique constraint) |
| Malformed key | `400` |

The key and a SHA-256 of the canonical body are stored on the report (`idempotency_key`, `request_fingerprint`, migration `0003`).

## Photos

Upload first, then attach by id when submitting (upload -> classify -> submit).

```
POST /api/v1/waste-reports/media?filename=bin.jpg
Content-Type: image/jpeg            (informational only)
<raw image bytes>
```

* **Raw body, not multipart.** No form parser is involved and the size limit is enforced **while streaming**, before the body is buffered (`MAX_UPLOAD_BYTES`, default 10 MiB; `413 payload_too_large`). A reverse proxy in front of the API must allow at least that size.
* **Nothing from the client is trusted.** The bytes are decoded; the detected format must be JPEG, PNG or WebP (`415 unsupported_media_type` otherwise, including SVG, GIF, PDF, empty and truncated files). The declared `Content-Type` and file name are ignored.
* **Re-encoded.** The stored file is a fresh encoding of the pixels: EXIF/XMP/ICC metadata (notably **GPS coordinates**) is removed, orientation is applied, and appended or polyglot payloads do not survive. Only the first frame of animated images is kept.
* **Size guards.** At least 32 px per side and at most 40 megapixels decoded (`422 invalid_image`), so a small file that expands to gigabytes is refused before decoding.
* **Storage.** Files are written under `FILE_STORAGE_LOCAL_PATH` with a generated name (`<2 hex>/<uuid>.<ext>`), mode 0600, atomically. The client file name is only a sanitised display label (`original_filename`); it never forms a path. The response does not expose storage keys or hashes.
* **Quota.** At most 20 photos per user may be waiting to be attached (`409 upload_quota_exceeded`).
* **Attaching.** A photo can be attached once, only by the user who uploaded it. An unknown, someone else's or already-used id all give the same `422 invalid_media`. Concurrent submissions cannot claim the same photo (row lock).
* **Download.** Served with the stored content type, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`, `Cache-Control: private, no-cache`, and a generated `Content-Disposition` file name. Browsers cannot send a bearer header from an `<img src>`: the web app must fetch the bytes through `apiRequest` and show a `blob:` URL.

## Listing

`GET /waste-reports?page=1&page_size=25&status=submitted&q=river&sort_by=reported_at&order=desc&reported_from=...&reported_to=...&mine=false`

* `page` >= 1, `page_size` 1-100. Response: `{items, total, page, page_size}`. Ordering is total (ties broken by id) so pages never repeat or skip rows.
* `status`: one of `submitted|under_review|verified|rejected|closed`.
* `q`: case-insensitive substring over title, description and address. `%`, `_` and `\` are matched literally. Max 100 characters.
* `sort_by`: `reported_at|title|status|estimated_weight_kg`; `order`: `asc|desc`. Anything else is 422.
* `reported_from` > `reported_to` is 400.
* Area: `min_latitude`, `max_latitude`, `min_longitude`, `max_longitude` together (WGS84 degrees, inclusive bounds). A box, not a named zone: zones have no boundary geometry. Reports without a location never match a box; a box that crosses the antimeridian is not supported. Giving some but not all four values, a minimum above its maximum, or a value outside -90..90 / -180..180 is 400 or 422. A citizen still only ever sees their own reports.

## Review workflow

`POST /waste-reports/{id}/review` with `{"status": "...", "reason": "..."}`.

| From | Allowed next states |
|---|---|
| `submitted` | `under_review`, `verified`, `rejected` |
| `under_review` | `verified`, `rejected` |
| `verified` | `closed` |
| `rejected` | `closed` |
| `closed` | none (terminal) |

Anything else is `409 invalid_status_transition` and changes nothing. `rejected` requires a `reason` (3-1000 characters). The row is locked during the change, so two simultaneous reviews apply exactly one transition. Each change writes an audit entry `waste_report.status_changed` with `from`, `to` and `reason`. There is no separate status-history table for reports; the audit log is the history.

## Audit events

`waste_report.created` (attachment count, whether idempotent), `waste_report.status_changed`, `waste_report.media_uploaded` (content type and size). Actor, request id and peer address are recorded.

## Not implemented

Editing or withdrawing a submitted report, deleting photos, automated purging of unattached uploads (an operator can find them with `media_assets.waste_report_id IS NULL`), and hand-off to classification and collection (later phases).
