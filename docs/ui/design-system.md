# UI design system

**Status:** minimal. One tokenized stylesheet and one component (`Badge`) exist. No UI framework has been selected; choosing one (or a headless library) requires an ADR comparing accessibility, bundle size and licence.

## Rules
- Reusable primitives live only in `frontend/src/components/ui/` (button, input, table, modal, ...). Do not create a second button, table or modal system inside a feature; extend the shared one.
- Shared app shells live in `components/layout/`; page-level feedback (not found, error fallback, empty/loading states) in `components/feedback/`.
- **Tokens** are CSS custom properties in `src/styles/global.css` (`--color-*`, `--radius`). Components use tokens, not hard-coded colours.
- **Accessibility** (WCAG 2.2 AA target): semantic landmarks (`header`, `main`, headings in order), every control labelled, keyboard operable with visible focus, state conveyed by text and not colour alone (the `Badge` always carries a word), errors announced with `role="alert"`.
- **Tests:** components are tested with Testing Library role/label queries, which doubles as an accessibility check.
- **Content:** user-facing errors come from `services/error-handler.ts`; never display raw server text for 5xx.
- **Data:** components display data from the API; no mock arrays or placeholder numbers in production UI. Demonstration data must be explicitly labelled and live in a designated demo location.
- **Navigation:** entries are added together with real features. There is no "Smart Bins & Telemetry" entry, and simulated sensor readings are never shown as live data.

## Current inventory
| Component | Path | Purpose |
|---|---|---|
| `Badge` (`success`, `danger`, `neutral`) | `components/ui/Badge.tsx` | Short status label |
| `AppLayout` | `components/layout/AppLayout.tsx` | Header + main outlet |
| `NotFound`, `RouteErrorFallback` | `components/feedback/` | Unknown route; render failure |
