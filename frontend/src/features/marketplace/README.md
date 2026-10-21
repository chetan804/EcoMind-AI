# Feature: marketplace

Surplus-material listings and requests (reference screen 08, "Circular Surplus Marketplace").

**Status:** implemented as a matching board with photos (up to 4, fetched through `AuthImage` because they need the session token), listing expiry and renewal, and a recorded outcome (handed over / withdrawn / expired). No price, payment, delivery or chat exist, on purpose: see `docs/api/marketplace-api.md`. Cards show the cover photo, or a category icon when there is none.

- **Backend module:** `marketplace` (`/api/v1/marketplace`)
- Server data comes from the shared API client through TanStack Query; no local mock data.
