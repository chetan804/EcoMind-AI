# Feature: landing

Public marketing page at `/`. It is outside the application shell and needs no authentication.

**Status:** implemented. Static content plus real screenshots; it calls no API.

- **Backend module:** none. This is the one frontend feature that is not a backend domain; it is registered in `scripts/quality/check_structure.py` as a known feature.
- **Structure:** `content.ts` holds every claim (facts, problems, capabilities, roles, security points, demo steps and screenshot captions). `pages/LandingPage.tsx` composes the 18 sections: hero, problem, solution, capabilities, classification, forecasting, anomaly, routing, command center, citizen participation, marketplace, traceability, impact and rewards, workflow, roles, security and transparency, final call to action, footer. `components/FeatureSection` and `ProductShot` render a text block beside a framed screenshot.
- **Header:** `PublicHeader` is `position: sticky` at `--z-sticky`, outside the hero (which has `overflow: hidden`). Section links, Sign in and Get started; below 1024 px the links move into a menu (`aria-expanded`, Escape closes and returns focus).
- **Watch demo:** `DemoDialog` is a native modal `<dialog>` (the page behind is inert, Escape and the X close it, focus returns to the button). It is a five-step walkthrough (classify, forecast, anomalies, routes, recovery) with a screenshot, what is built and what the limit is. It is deliberately not a video player. The earlier button was built with `unavailableReason`, which makes `Button` ignore clicks by design; that is why it did nothing.
- **Screenshots:** `frontend/public/landing/*.webp` (1200 px wide, 28 to 45 KB each) are captures of the running application on the labelled demonstration data from `scripts/demo/seed_demo.py`. Retake them after a visible UI change (see `docs/operations/supervised-demo.md`).
- **Honesty:** the facts are counts of things that exist (5 roles, 10 sorting-guide categories, 3 ML capabilities, 0 approved classifiers). No customers, partners, certifications, accuracy, cost, carbon or landfill figures appear, because none can be substantiated. Keep every statement true when features change; `frontend/tests/integration/ui-pages.test.tsx` checks the sections, the demo dialog and the absence of accuracy claims.
- **Public interface:** `import { LandingPage } from '@/features/landing'`.
- **Design:** see `docs/ui/design-system.md` (deviations 2 and 3).
