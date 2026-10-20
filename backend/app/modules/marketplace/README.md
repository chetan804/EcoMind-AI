# Marketplace (`marketplace`)

Surplus-material listings that facility operators and managers offer for reuse, and the requests other users make for them.

**Status:** implemented (listings, lifecycle, requests, accept/decline/withdraw, notifications, audit). It is a matching board: no price, payment, delivery, photos or chat. See docs/api/marketplace-api.md.

## Ownership
- **Tables owned:** `marketplace_listings`, `marketplace_requests`
- **Files present:** `models.py`, `constants.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`.

## Relationships
- **Depends on (via services / foreign keys):** `users`, `facilities` (optional listing facility), `notifications`, `audit`
- Other modules must use this module's `service.py`; never write to its tables directly.

## API
`/api/v1/marketplace`, registered in `app/api/v1/router.py`.

## Notes
- Listing transitions live in `constants.LISTING_TRANSITIONS`; `reserved` is reached only by accepting a request.
- Decisions lock the listing row (`SELECT ... FOR UPDATE`) so two requests cannot both be accepted.
- Permissions are seeded by migration 0010 and mirrored in `app/modules/users/rbac.py` (drift-guard test).

## Tests
`backend/tests/api/test_marketplace.py` (permissions, visibility, lifecycle, request rules, privacy, filters, constraints, notifications, audit). Run: `make test-backend`.
