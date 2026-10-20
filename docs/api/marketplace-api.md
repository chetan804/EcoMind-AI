# Marketplace API

Base path `/api/v1/marketplace`. Facility operators and managers list surplus material or items for reuse; other signed-in users browse and ask for what they need; the owner decides.

**This is a matching board, not a shop.** There is no price, payment, delivery, escrow, rating, photo upload or chat. A request only tells the owner that someone is interested and carries the requester's e-mail address so the two can arrange hand-over themselves.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /marketplace/listings` | `marketplace:read` | List and search (visibility rules below) |
| `POST /marketplace/listings` | `marketplace:create` | Create a **draft** owned by the caller (`201`) |
| `GET /marketplace/listings/{id}` | `marketplace:read` | One listing |
| `PATCH /marketplace/listings/{id}` | `marketplace:read` + owner or `marketplace:manage` | Edit a draft or published listing |
| `POST /marketplace/listings/{id}/publish` | owner or `marketplace:manage` | draft → published |
| `POST /marketplace/listings/{id}/close` | owner or `marketplace:manage` | Withdraw or finish a listing; body `{"reason"}` is optional |
| `POST /marketplace/listings/{id}/requests` | `marketplace:request` | Ask for a published listing (`201`) |
| `GET /marketplace/listings/{id}/requests` | owner or `marketplace:manage` | Who asked, with contact e-mail |
| `GET /marketplace/requests/mine` | `marketplace:request` | The caller's own requests (paginated) |
| `POST /marketplace/requests/{id}/accept` | owner or `marketplace:manage` | Accept a pending request |
| `POST /marketplace/requests/{id}/decline` | owner or `marketplace:manage` | Decline a pending request, or release an accepted one |
| `POST /marketplace/requests/{id}/withdraw` | the requester | Withdraw a pending or accepted request |

**Roles.** Citizen and collector: browse and ask. Facility operator: browse, ask and offer. Manager: also act on any listing. Administrator: everything.

## Fields

`title` (3–200), `description` (optional), `category` (`plastics`, `metals`, `paper`, `glass`, `e_waste`, `organics`, `textiles`, `wood`, `furniture`, `other`), `quantity` (> 0, up to 3 decimals, serialised as a string), `unit` (`kg` or `units`), `condition` (`like_new`, `good`, `fair`, `damaged`), optional `facility_id` (must exist) and `pickup_city`. Unknown fields (for example `price`) are rejected with `422`.

Responses add `facility_name`, `owner_name`, `is_mine`, `my_request_status`, and `pending_request_count`, which is `null` unless the caller owns the listing or holds `marketplace:manage`.

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

## Notifications and audit

New request → the owner; accept, decline, close → the requester; withdrawal → the owner. They appear in the in-app notification list under category `system` (there is no separate marketplace category: adding one would change an existing constraint). The audit log records `marketplace_listing.created|updated|published|closed` and `marketplace_request.created|accepted|declined|withdrawn`.

## Not implemented

Photos, prices, payment, delivery, ratings, quantity partially fulfilled by several requests, expiry of listings, and links from a listing to a recovery record or material passport.
