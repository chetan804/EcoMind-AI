# Rewards and impact ledger API

Base path `/api/v1/rewards`.

| Method and path | Permission | Purpose |
|---|---|---|
| `GET /rewards/me/balance` | `rewards:read_own` | Own points, earned points, impact weight, entry count |
| `GET /rewards/me/entries` | `rewards:read_own` | Own entries (`entry_type`) |
| `GET /rewards/ledger` | `rewards:manage` | Whole ledger (`user_id`, `entry_type`, `source_type`) |
| `GET /rewards/ledger/summary` | `rewards:manage` | Totals across users |
| `POST /rewards/adjustments` | `rewards:manage` | Signed manual adjustment with a mandatory reason (`201`) |
| `POST /rewards/entries/{id}/reverse` | `rewards:manage` | Cancel one positive entry once (`201`) |
| `GET /rewards/catalog` | `rewards:read_own` | Items the caller can spend points on |
| `POST /rewards/catalog/{id}/redeem` | `rewards:redeem` | Spend points (`201`, or `200` when `client_request_id` repeats) |
| `GET /rewards/me/redemptions` | `rewards:read_own` | Own redemptions with their claim codes |
| `POST /rewards/me/redemptions/{id}/cancel` | `rewards:redeem` | Cancel an own, still pending redemption |
| `GET /rewards/items`, `POST /rewards/items`, `PATCH /rewards/items/{id}` | `rewards:manage` | Staff run the catalogue (no delete: switch an item off) |
| `GET /rewards/redemptions` | `rewards:manage` | Redemption queue (`status`, `code`, `user_id`) |
| `POST /rewards/redemptions/{id}/fulfil` | `rewards:manage` | Mark handed over (optional `note`) |
| `POST /rewards/redemptions/{id}/cancel` | `rewards:manage` | Cancel with a mandatory `reason` |

Only citizens (and administrators) hold `rewards:read_own`; collectors and operators do not earn rewards (`403`).

## How points are earned

Not through this API: when a collection task created from a **verified** citizen report is **completed** with a collected weight, the reporter receives `round(weight_kg × REWARD_POINTS_PER_KG)` points (default 10; at least 1). The entry is idempotent per user and task (`docs/api/collections-api.md`). Tasks without a verified report earn nothing.

## Impact

`impact_weight_kg` is the collected weight in kilograms (earned entries minus reversed ones). **No carbon or other environmental coefficient is applied**: none is sourced, and none is invented. The `basis` field repeats this.

## Corrections

The ledger is append-only, enforced by a database trigger (migration 0007) as well as by the code. Corrections are new rows:

* **Adjustment** (`entry_type=adjustment`, `source_type=manual`): non-zero points within ±100,000, `description` required. A debit that would take the balance below zero is `409 insufficient_balance`; balance changes are serialised per user.
* **Reversal**: cancels exactly one earned or positive-adjustment entry with negative points and the same weight; reversing twice is `409 entry_already_reversed`; reversals and debits cannot be reversed (`422`).

The affected user receives an in-app notification. Audit events: `reward.adjusted`, `reward.reversed`.

## Catalogue and redemption

**The platform ships no rewards.** There is no seeded catalogue, partner or monetary value: staff (`rewards:manage`) enter items, and points have only the meaning the operating organisation gives them. A catalogue is empty until staff add items.

An item has a `name`, optional `description`, `points_cost` (1 to 1,000,000), optional `stock` (`null` is unlimited), optional `max_per_user`, an `active` switch and an optional `valid_until` (must carry a time zone). `PATCH` follows partial-update semantics: only the fields sent change, and `name`, `points_cost` and `active` cannot be set to `null`. Items are never deleted, because redemptions refer to them; switch one off instead. Each redemption keeps a snapshot of the item name and cost.

Citizens see items that are active and unexpired. An item with no stock left is listed with `available=false` and `unavailable_reason` (`out_of_stock` or `limit_reached`). Inactive and expired items answer `404`.

### Redeeming

`POST /rewards/catalog/{id}/redeem` with `{"client_request_id": "<uuid>"}`; the client picks a new id for each deliberate attempt and reuses it when retrying a request whose answer it never saw.

* Success: `201` and a redemption with `status=pending` and a claim code such as `K7M2P-9XQ4T`. The ledger gets a negative `redeemed` entry (`source_type=reward_redemption`, `source_id` is the redemption id), stock goes down, an audit row `reward.redeemed` is written and the citizen is notified with the code.
* Repeating the same `client_request_id` for the same item returns the original redemption with `200` and spends nothing. Using it for another item is `409 client_request_id_reused`.
* `404` unknown, inactive or expired item; `409 reward_unavailable` (out of stock); `409 redemption_limit_reached` (non-cancelled redemptions of the item reached `max_per_user`); `409 insufficient_balance`. A refused request writes nothing.

The user row is locked first and the item row second, in every operation, so simultaneous requests cannot overspend a balance or sell the last unit twice (covered by race tests).

### Hand-over and cancellation

`pending` → `fulfilled` (staff hand the reward over; terminal) or `pending` → `cancelled` (terminal). A cancellation appends a positive `reversal` entry pointing at the `redeemed` entry, returns the unit to stock and notifies the citizen when staff cancel. Citizens can cancel their own pending redemptions; staff must give a reason. Any further change to a fulfilled or cancelled redemption is `409 invalid_redemption_state`. `POST /rewards/entries/{id}/reverse` rejects `redeemed` entries (`422`): the redemption workflow is the only way back.

Staff see the owner's name and e-mail on the queue (they need to know whom to hand the reward to); citizens never do. Audit events: `reward_item.created`, `reward_item.updated`, `reward.redeemed`, `reward.redemption_fulfilled`, `reward.redemption_cancelled`.

Operations: migration 0014 adds the tables and the `rewards:redeem` permission (citizen, administrator). It cannot be downgraded once redemptions exist, because the append-only ledger would keep entries the older schema forbids.

## Not implemented

Delivery, shipping addresses, monetary value, partner integrations, partial fulfilment and expiry of unredeemed points.
