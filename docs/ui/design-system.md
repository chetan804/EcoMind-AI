# UI design system

**Status:** Stage 1 of the UI milestone is implemented: tokens, a shared component library, the application shell, and four screens (Landing, Sign in / Sign up, Operational Command Center, AI Waste Classification). Eighteen further screens are **not started** (Stage 2). See `screen-inventory.md`.

The UI is plain CSS (custom properties plus one stylesheet per component) on React. No UI framework or headless library was added: the interactive primitives use native elements (`<dialog>`, `<button>`, `<input>`) so the browser supplies focus handling, and each has role/keyboard tests.

## Rules

- Reusable primitives live only in `frontend/src/components/ui/`. Do not build a second button, table or dialog inside a feature; extend the shared one.
- Shell and page chrome are in `components/layout/` and `components/navigation/`; feedback (alerts, empty/loading states, not-found, planned-feature page, demo-data notice) in `components/feedback/`; charts and metric tiles in `components/data-display/`.
- Components use **tokens**, never hard-coded colours or one-off sizes. Where a value was measured against the design references and has no token yet, add a token (for example `--text-title`, `--text-stat`).
- **Accessibility target: WCAG 2.2 AA.** Landmarks and heading order; every control labelled; visible keyboard focus; state is never conveyed by colour alone; errors use `role="alert"`, other messages `role="status"`; touch targets are at least 44 px; `prefers-reduced-motion` is respected.
- **Honesty rules** (binding, from the project constraints):
  - Fixtures live in the owning feature's `fixtures/` folder and every region that shows them carries a visible `DemoDataNotice` ("Demonstration data, not live" or "Sample layout").
  - No model accuracy, confidence or prediction is ever shown as real. The classification layout preview is labelled "Sample layout", shows "Model: Not connected" and "Evaluation: Not evaluated", and has no percentage.
  - Actions that need a missing backend are rendered with `unavailableReason`: the control is `aria-disabled`, keeps focus, ignores activation, and explains why through an accessible description. They are never silently inert and never fake success.
  - The greeting is time-of-day only: no invented user name.
  - Marketing figures from the references (85 %, 40 %, 2.5x, 1000+) are **not used**. See *Deviations*.
- **Navigation:** the sidebar lists the product's planned destinations. Items without a feature are tagged "Soon" and route to a "planned, not built" page (`PlannedFeaturePage`) that says so plainly; they are generated from `components/navigation/nav-items.ts` (`status: 'planned'`). **There is no "Smart Bins & Telemetry" entry and no "Bins" entry**, even though the reference sidebar shows "Bins" (excluded by product decision; asserted by tests).
- **Data:** components display data passed to them. Real data comes from the API client through TanStack Query; there are no mock arrays as production sources.

## Themes and tokens

Defined in `src/styles/tokens.css` (values), `base.css` (reset, typography, utilities) and `global.css` (imports). Dark is the default (`:root`, `[data-theme='dark']`). The light theme applies when `data-theme="light"` is set on the root element; there is **no theme switcher and no `prefers-color-scheme` detection yet** (Stage 2). Light keeps the **dark sidebar** on every screen. Surfaces are flat; gradients appear only where the references show them (primary button highlights, hero scrim).

| Token group | Values |
|---|---|
| Dark surfaces | background `#061a27`, sidebar `#05141b`, card `#0c202b`, raised `#112631`, field `#14293a`, auth panel `#1f3045` |
| Borders | `#17313b`, strong `#26485a` |
| Text | primary `#f2f7f8`, secondary `#b4c3ca`, muted `#86a0ab` |
| Accent | primary mint `#7af794`, teal `#2fe3b0`, danger `#f24d54`, nav-active `#047a56` |
| Radii | 8 / 12 / 16 / 24 px |
| Layout | sidebar 256 px, top bar 72 px, control height 44 px (56 px large), touch target 44 px |
| Type | Inter Variable (self-hosted via `@fontsource-variable/inter`); scale 12 / 13 / 14 / 16 / 18 / 20 / 22 (card titles) / 24 / 28 (metric values) / 32 (page titles) / up to 64 (landing hero, fluid) |
| Icons | `lucide-react`, 1.75 stroke |
| Breakpoints | 1023 px (sidebar becomes a drawer), 767 px, 479 px |

Computed contrast (WCAG): primary text 15.5:1, secondary 9.2:1, muted 4.9 to 6.4:1 on dark surfaces; text on primary 11.8:1; white on nav-active 5.35:1. **The light-theme values are provisional estimates**: only dark screens exist in Stage 1, and the light palette will be finalised and contrast-checked against the light reference screens in Stage 2.

## Component inventory

| Area | Components |
|---|---|
| `components/ui/` | `Button`, `ButtonLink`, `IconButton`, `IconLink`, `Badge`, `Card`/`CardHeader`, `Field`, `Input`, `PasswordInput`, `SearchInput`, `Select`, `Textarea`, `Checkbox`, `Switch`, `Radio`/`RadioGroup`, `Tabs`, `Dialog`/`ConfirmDialog`, `Menu`, `Tooltip`, `ProgressBar`, `Avatar`, `Breadcrumbs`, `Table`, `Pagination` |
| `components/feedback/` | `Alert`, `EmptyState`, `Spinner`, `Skeleton`, `DemoDataNotice`, `PlannedFeaturePage`, `NotFound`, `RouteErrorFallback`, `ToastProvider` (library only; not mounted in `Providers` until a feature needs it) |
| `components/data-display/` | `MetricTile`, `Legend`, `TrendChart`, `DonutChart` |
| `components/layout/` | `AppShell`, `PageHeader`, `Topbar`, `UserTools`, `BrandMark`/`Brand` |
| `components/navigation/` | `Sidebar`, `PageSearch`, `nav-items.ts` |

Behaviours worth knowing:

- `Field` wires label, hint and error to the control (`aria-describedby`, `aria-invalid`, `aria-required`); pass it a render function.
- `Dialog` uses native `showModal()`; mark the element that should receive focus on open with `data-autofocus` (React's `autoFocus` runs before the dialog is open, so the browser would otherwise focus the close button).
- `Menu` follows the WAI-ARIA menu-button pattern: arrow keys, Home/End, Escape from anywhere (trigger or item), focus returns to the trigger, outside click closes.
- `TrendChart` and `DonutChart` always expose their data as a visually hidden table or labelled list; empty series render an explicit empty state, never an empty chart.
- Visually hidden tables must be wrapped in a `.visually-hidden` `div`: a `<table>` ignores width and `overflow` on itself and caused horizontal scrolling on phones.

## Reference material and how fidelity was checked

The 22 reference PNGs in `docs/ui/reference/` (with `manifest.json`, which records each file's SHA-256) are crops of **one blurry, AI-generated 1536 x 1024 composite**, and their text is partly illegible. They guide layout, proportion and tone; they are not specifications, and nothing here is "pixel-perfect". References 01 to 04 are dark; 05 to 07 have a dark sidebar with light content; 08 to 22 are Stage 2.

- A generative super-resolution pass (Real-ESRGAN, 4x) was produced as a **viewing aid only**. It sharpens edges but **invents detail and text**, so it was never used as a source for copy, numbers or colours (colours were sampled from the original pixels). The 22 MB of outputs are generated artefacts and are deliberately **not committed**.
- No reference crop is used as an asset. All illustrations (landing scene, sign-in art, sample bottle, map) are original inline SVG/CSS.
- `tests/e2e/visual/` holds a repeatable developer workflow (see its README): render each screen in real Chromium at a viewport derived from the reference's proportions, **downscale the render to the reference's pixel size** (the reference is never enlarged), then report landmark geometry deltas in design pixels plus SSIM and colour error. Landmark boxes were read by eye from the blurry references, so expect roughly +/-5 design px of reading error; the numbers drive iteration, not acceptance.

### Result at the last comparison (design px; positive = mine is further right / lower / larger)

| Screen (viewport) | Geometry | Notes |
|---|---|---|
| Landing (1440 x 852) | CTA 0 to +1; feature row top +1, width -4; header CTA 0 vertically | SSIM 0.32: the hero scene is original SVG, far simpler than the photographic reference |
| Sign in (910 px card) | brand panel edge -1; fields keep the reference rhythm (within 5 px of each other) but start ~49 px higher | form top padding deliberately shortened, see Deviations |
| Command Center (1440 x 836) | sidebar +3; KPI top +3; trend/map -3; third row +4; widths within ~7 | SSIM 0.57 |
| Classification (1200 x 930) | upload card -6 top, -3 bottom; result -6 top; classes -3 top | widths within ~14 |

Responsive checks (full page at 1280, 768 and 390 px): zero horizontal overflow on all four screens, enforced by Playwright (`tests/e2e/specs/ui-shell.spec.ts`).

## Deviations from the references (deliberate)

1. **"Bins" navigation item omitted.** Excluded by product decision. The KPI that the reference labels "Active Bins" is "Open reports" with demo data; the map legend uses Reports / Collections / Facilities / Alerts.
2. **Landing statistics replaced.** The reference's 85 % classification accuracy, 40 % lower collection cost, 2.5x faster response and 1000+ citizens have no evidence behind them. The strip shows verifiable repository facts instead: 19 planned modules, 6 waste classes in scope, 3 planned ML capabilities, **0 models trained so far**. Changing this is a product-copy decision for the owner.
3. **Landing "Watch demo"** is rendered unavailable (no demo exists). The page adds an "early development" note and a footer disclosure that the reference does not have.
4. **Greeting** is "Good morning / afternoon / evening" with no name or emoji.
5. **Demo-data notices** appear on the dashboard (header, right side) and classification layout preview. The reference has none.
6. **Classification screen:** the reference shows a result, a confidence percentage, a model name and a dataset source (the text is partly illegible). None of that exists. The page starts empty, previews a chosen image locally (nothing is uploaded), and says classification is not available. A "Show layout preview" switch under the result card shows labelled sample content. "Verify result" is unavailable. The class grid is titled "Planned waste classes".
7. **Sign in / Sign up:** a valid submission sends nothing and reports "not available yet". Google, Microsoft and "Forgot password?" are unavailable with reasons. The password minimum of **12 characters is provisional**: `docs/security/security-baseline.md` leaves the policy to the sign-up milestone.
8. **Sign-in card geometry:** the reference card is cropped, so its true height is unknown. Matching the form's start position would need a card about 930 px tall (scrolling on a laptop), so the form starts ~49 px higher than the reference.
9. **Unreadable elements omitted:** the small element left of the dashboard search field is illegible in the reference and is not reproduced. The reference sidebar spacing varies from item to item; the shell uses a uniform 48 px item height (the active pill measures about 55 px in the reference, which is a rendering artefact). The "showcase" frame around each crop is ignored.
10. **Routing:** `/` is now the landing page (previously a redirect to System status). System status moved to its real route, `/settings/system-status`. The existing routing and e2e tests were updated for that and nothing was weakened.

## Testing the UI

- `tests/components/` and `tests/unit/`: role/label based tests for primitives, overlays (tabs, dialog, menu), charts, upload validation and form schemas.
- `tests/integration/`: routing, navigation (including the absence of Smart Bins), planned pages, page search, the dashboard demo notice, sign-in/up flows with a spy proving no network call, and the classification flow including that no result is produced.
- jsdom has no `<dialog>` modal API; `tests/setup.ts` installs a minimal stand-in. Focus trapping, Escape and mobile overflow are therefore verified in real Chromium by `tests/e2e/specs/ui-shell.spec.ts` (needs only the frontend, no API).

## Open items for Stage 2

- The 18 remaining screens (references 05 to 22) and the light theme: finalise light tokens and contrast-check them.
- Route-level code splitting: the single bundle is about 535 kB (166 kB gzipped) and Vite warns above 500 kB.
- Mount `ToastProvider` when the first feature needs notifications.
- Real authentication and the account menu contents, once the auth milestone exists.
