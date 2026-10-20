# Feature: marketplace

Surplus-material listings and requests (reference screen 08, "Circular Surplus Marketplace").

**Status:** implemented as a matching board. No price, payment, delivery, photos or chat exist; cards show a category icon instead of a photo. See `docs/api/marketplace-api.md`.

- **Backend module:** `marketplace` (`/api/v1/marketplace`)
- Server data comes from the shared API client through TanStack Query; no local mock data.
