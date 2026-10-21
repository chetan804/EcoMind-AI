# Feature: rewards

Points balance, impact ledger, reward catalogue and hand-over redemption.

**Status:** implemented (see `docs/ui/screen-inventory.md` for the screen and `docs/api/rewards-api.md` for the API).

- **Backend module:** `rewards`
- **Screen:** `pages/RewardsPage.tsx`, with `components/CatalogueTabs.tsx` (citizen: catalogue, redeem, my redemptions) and `components/StaffTabs.tsx` (staff: ledger and adjustments, items, redemption queue). The tabs shown follow the signed-in user's permissions; the server enforces them again.
- **Redemption rules the UI relies on:** each attempt carries a fresh `client_request_id` so a double click or retry spends once; the citizen receives a claim code (`XXXXX-XXXXX`) to show at the counter; staff mark it fulfilled or cancel it (a cancel refunds the points). A refused attempt (`reward_unavailable`, `redemption_limit_reached`, `insufficient_balance`, ...) shows the server's message through `getErrorMessage`; the screen does not interpret the codes itself. Nothing is shipped or paid by the platform.
- **Layout:** `api/`, `components/`, `hooks/`, `pages/` and an `index.ts` that is the feature's only public interface. Other code imports `@/features/rewards`, never its internals (enforced by ESLint).
- Server data comes from the shared API client (`@/services/api-client`) through TanStack Query; no local mock data as a production source.
