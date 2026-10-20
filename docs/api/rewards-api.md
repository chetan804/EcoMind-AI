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

## Not implemented

**Redemption.** The ledger has a `redeemed` entry type, but no reward catalogue, partner or value exists, and none is invented here.
