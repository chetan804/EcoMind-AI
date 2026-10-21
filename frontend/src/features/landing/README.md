# Feature: landing

Public marketing page at `/`. It is outside the application shell and needs no authentication.

**Status:** UI implemented (Stage 1 UI milestone). Static content only: it calls no API.

- **Backend module:** none. This is the one frontend feature that is not a backend domain; it is registered in `scripts/quality/check_structure.py` as a known feature.
- **Contents:** `PublicHeader` (in-page anchor navigation, "Get started" to `/sign-up`), hero with an original layered SVG scene (`HeroArt`, geometry in `hero-scene.ts`; scrims measured for text contrast), a statistics strip, four capability cards, Impact and About sections, an "under active development" note and a footer disclosure.
- **Honesty:** the strip shows verifiable repository facts (5 user roles, 6 waste classes the classifier knows, 3 ML capabilities built, **0 classifiers approved for use**), not the marketing figures in the design reference (85 %, 40 %, 2.5x, 1000+), which have no evidence. "Watch demo" is an unavailable control with a reason. Replacing the strip with real product metrics, or changing the copy, is a product decision for the owner.
- **Public interface:** `import { LandingPage } from '@/features/landing'`.
- **Design:** see `docs/ui/design-system.md` (deviations 2 and 3).
