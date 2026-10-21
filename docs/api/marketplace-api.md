# Marketplace API

Base path `/api/v1/marketplace`. Facility operators and managers list surplus material or items for reuse; other signed-in users browse and ask for what they need; the owner decides.

**This is a matching board, not a shop.** There is no price, payment, delivery, escrow, rating or chat (see *Not implemented* for why). A request only tells the owner that someone is interested and carries the requester's e-mail address so the two can arrange hand-over themselves.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /marketplace/listings` | `marketplace:read` | List and search (visibility rules below) |
| `POST /marketplace/listings` | `marketplace:create` | Create a **draft** owned by the caller (`201`) |
| `GET /marketplace/listings/{id}` | `marketplace:read` | One listing |
| `PATCH /marketplace/listings/{id}` | `marketplace:read` + owner or `marketplace:manage` | Edit a draft or published listing |
| `POST /marketplace/listings/{id}/publish` | owner or `marketplace:manage` | draft → published; optional body `{"duration_days": 1–90}` |
| `POST /marketplace/listings/{id}/renew` | owner or `marketplace:manage` | Keep a published listing on offer for another period, counted from now; same optional body |
| `POST /marketplace/listings/{id}/photos` | owner or `marketplace:manage` | Attach one photo (raw body: JPEG, PNG or WebP; query `caption` optional; `201`) |
| `DELETE /marketplace/listings/{id}/photos/{photo_id}` | owner or `marketplace:manage` | Remove a photo (`204`) |
| `GET /marketplace/photos/{photo_id}/content` | `marketplace:read` | The image, under the same visibility rules as its listing |
| `POST /marketplace/listings/{id}/close` | owner or `marketplace:manage` | Withdraw or finish a listing; optional body `{"reason", "outcome": "handed_over"\|"withdrawn"}` |
| `POST /marketplace/listings/{id}/requests` | `marketplace:request` | Ask for a published listing (`201`) |
| `GET /marketplace/listings/{id}/requests` | owner or `marketplace:manage` | Who asked, with contact e-mail |
| `GET /marketplace/requests/mine` | `marketplace:request` | The caller's own requests (paginated) |
| `POST /marketplace/requests/{id}/accept` | owner or `marketplace:manage` | Accept a pending request |
| `POST /marketplace/requests/{id}/decline` | owner or `marketplace:manage` | Decline a pending request, or release an accepted one |
| `POST /marketplace/requests/{id}/withdraw` | the requester | Withdraw a pending or accepted request |

**Roles.** Citizen and collector: browse and ask. Facility operator: browse, ask and offer. Manager: also act on any listing. Administrator: everything.

## Fields

`title` (3–200), `description` (optional), `category` (`plastics`, `metals`, `paper`, `glass`, `e_waste`, `organics`, `textiles`, `wood`, `furniture`, `other`), `quantity` (> 0, up to 3 decimals, serialised as a string), `unit` (`kg` or `units`), `condition` (`like_new`, `good`, `fair`, `damaged`), optional `facility_id` (must exist) and `pickup_city`. Unknown fields (for example `price`) are rejected with `422`.

Responses add `expires_at`, `is_expired`, `outcome` (`handed_over`, `withdrawn`, `expired`; `null` while open and on listings closed before outcomes were recorded), `photos` (`id`, `position`, `caption`, `width_px`, `height_px`), `facility_name`, `owner_name`, `is_mine`, `my_request_status`, and `pending_request_count`, which is `null` unless the caller owns the listing or holds `marketplace:manage`.

## Visibility

Published and reserved listings are visible to everyone who can read. Drafts and closed listings are visible only to their owner and to managers; to anyone else they answer `404`, the same as a missing id. Likewise, deciding on a request that is not yours answers `404`.

List filters: `mine`, `category`, `status`, `q` (title, description, city; wildcards are literal), `sort_by` (`created_at`, `title`, `quantity`), `order`, `page`, `page_size`.

## Lifecycle

```
draft ─► published ◄─► reserved
  │          │             │
  └──────────┴─────────────┴──► closed   (final)
```

* `reserved` is entered only by accepting a request and left only by releasing it (decline or withdraw of the accepted request) or by closing.
* Any other move, editing a reserved or closed listing, or publishing twice is `409 invalid_listing_state`.

## Requests

* Only on **published** listings (`409 invalid_listing_state` otherwise), never on your own (`409 own_listing`), and one per user and listing (`409 request_exists`).
* A withdrawn request can be made again; it is the same row, back to `pending`. A declined request cannot.
* Accepting a request declines every other pending request on that listing.
* Closing a listing declines pending requests; an accepted request stays as history.
* A request that is not in a state that allows the action is `409 invalid_request_state`.
* The requester's e-mail is returned only to the listing owner, to managers and to the requester.

## Expiry

A listing that nobody renews should not stay on offer for ever (stale offers waste requesters' time).

* Publishing sets `expires_at` to now + `duration_days` (default `MARKETPLACE_LISTING_DAYS`, 30; allowed 1–90). Renewing counts again from now and re-arms the warning below.
* From `expires_at` a **published** listing is `is_expired`: other people no longer see it (`404`, like a draft), it cannot be requested (`409 listing_expired`), and the owner and managers still see it and can renew it. A **reserved** listing never expires: it is being handed over.
* The daily job `python -m app.cli expire-marketplace-listings` makes it official: status `closed`, outcome `expired`, reason "The listing expired"; pending requests are declined and their requesters told; the owner is told. It is idempotent, audited (`marketplace_listing.expired`) and safe to run as often as you like. The platform has no scheduler, so run it from cron or a timer (see the runbook). Until it has run, the API already behaves as described.
* The same job warns the owner once, 3 days before expiry ("Your listing expires soon").
* Listings that were on offer when migration 0013 was applied got 30 days from the migration, so deploying it closes nothing.

## Closing and outcomes

`close` records how a listing ended. Without `outcome` it is `withdrawn`. `handed_over` is accepted only for a **reserved** listing (one with an accepted request); the accepted requester is told the hand-over was recorded. Closing a reserved listing as withdrawn tells that requester too. `expired` is set only by the job. These outcomes are what the board can honestly report about reuse; nothing is measured beyond what owners record.

## Photos

* At most **4** per listing (`409 photo_limit_reached`); only while the listing is a draft or published (`409 invalid_listing_state` otherwise); owner or manager only.
* The body is the raw image. The size limit is `MAX_UPLOAD_BYTES` (default 10 MiB), enforced while streaming (`413`); the bytes are decoded and **re-encoded**, so EXIF/GPS metadata, trailing data and polyglot payloads do not survive; the type is detected from the bytes, never from the header (`415` for anything but JPEG, PNG, WebP; `422` for images under 32 px or with too many pixels).
* Photos are visible to whoever can see the listing, and to nobody else (`404`). The content endpoint answers with `nosniff`, `Content-Security-Policy: default-src 'none'; sandbox` and `Cache-Control: private, no-cache`, and needs the access token, so the web app fetches it through `apiRequest` (an `<img src>` cannot send the header).
* A failed database write removes the file, and deleting a photo removes the file after the row is gone; a crash between the two can leave an orphan file, never a dead link. `position` numbers are never reused.
* Stored through the file-storage integration (local disk today, like report photos). There is no moderation of image content; managers can remove any photo.

## Notifications and audit

New request → the owner; accept, decline, close → the requester; withdrawal → the owner. They appear in the in-app notification list under category `system` (there is no separate marketplace category: adding one would change an existing constraint). The audit log records `marketplace_listing.created|updated|published|renewed|closed|expired|photo_added|photo_removed` and `marketplace_request.created|accepted|declined|withdrawn`.

## Not implemented

Deliberately left out, because they are not a coding task:

* **Prices and payment, escrow, delivery, ratings.** Taking money between users makes the operator a marketplace operator in law: payment-provider contracts, KYC, tax and consumer-protection duties, dispute handling. The board stays a free hand-over matching service until an owner decides to take that on. A price field without payment would be a promise nobody can enforce, so there is none.
* **Chat.** Requests carry a message and the requester's e-mail, so the two parties talk outside the platform. In-app chat would need moderation and abuse handling.

Not built yet: quantity fulfilled partly by several requests, image-content moderation, and links from a listing to a recovery record or material passport.
