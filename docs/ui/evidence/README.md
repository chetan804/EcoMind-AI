# Visual evidence: Stage 1 UI verification and refinement

Real-browser captures of the four built screens compared with the design references in `docs/ui/reference/`. These guide iteration. **They do not demonstrate pixel-perfect fidelity**: the references are blurry crops of one AI-generated composite, and the landmark boxes were read by eye (about +/-5 design px of reading error). Numbers are a guide, never an acceptance test.

## Files

For each of `landing`, `sign-in`, `dashboard`, `classification`:

| File | What it is |
|---|---|
| `<screen>-render.png` | the screen in Chromium at the viewport used for that reference (1440 x 852, 910 x 844, 1440 x 836, 1200 x 930), real DOM output, no editing |
| `<screen>-sidebyside.png` | reference (left, never enlarged) and my render downscaled to the reference's pixel size (right), shown at the same scale |
| `<screen>-diff.png` | per-pixel difference at the reference's size |
| `responsive-contact-sheet.jpg` | all four screens at 1440 x 900, 768 x 1024 and 390 x 844 (viewport only) |

## Metrics at the final commit

| Screen | SSIM | Mean abs colour error | Colour grid mean / worst cell |
|---|---|---|---|
| Landing | 0.340 | 37.3 / 255 | 34.6 / 105.6 |
| Sign in | 0.523 | 28.4 / 255 | 30.3 / 103.8 |
| Dashboard | 0.573 | 13.5 / 255 | 9.1 / 21.5 |
| Classification | 0.538 | 18.1 / 255 | 8.3 / 37.6 |

Before this milestone (Stage 1 as merged): landing 0.322, sign-in 0.509, dashboard 0.573, classification 0.533.

Landmark deltas (design px; positive = mine is further right / lower / larger):

- Landing: Get started L -13 R -13, vertical 0 to -1; H1 left +5; Explore CTA L +8, vertical 0 to -1; feature card 1 top +1, width -4.
- Sign in: illustration panel right edge -1; email input top -49, password -54, button -43 (form starts higher by design, see below).
- Dashboard: sidebar right +3; KPI row top +3, bottom 0; trend, map top +1 bottom 0; alerts, composition, impact top -1; right edges -7 to +3 (first KPI card +24, a landmark misreading, see below).
- Classification: sidebar +5; upload card top 0 bottom 0; result card top 0 bottom 0, right -14; classes card top 0, right -14.

Before this milestone the dashboard trend and map cards were up to 11 px too tall and classification cards up to 14 px off vertically.

## Remaining deviations per screen (honest list)

**Landing.** The hero is original vector art following the reference composition; the reference is a photograph, so texture, lighting and detail differ a lot (the low SSIM is expected). No licensed photograph was available and none was invented. "Watch demo" is disabled because no demo exists. The stats strip shows repository facts instead of the reference's unsupported claims. Header and left text sit on scrims chosen for measured contrast.

**Sign in.** The form starts about 49 px higher than in the reference. Matching it would need a card roughly 930 px tall, which forces scrolling on a laptop; that was rejected. Google, Microsoft and "Forgot password?" are unavailable with reasons; submitting sends nothing. The brand mark is the shared leaf mark, not the reference's recycling glyph.

**Dashboard.** Demo data is labelled; the map is a stylised sample layout with arbitrary pins; no live metrics. "Bins" is omitted by product decision. The first KPI card shows +24 on its right edge, but the reference's own pixels put the gap between cards 1 and 2 at about x 170 to 175 reference px while the landmark file says 164, so the true offset is roughly +4; `targets.json` was left unchanged.

**Classification.** No result is shown because no model or inference endpoint exists: the screen offers a local preview, a labelled "Show layout preview" sample, and "Not connected" model state. The class tiles are titled "Planned waste classes". Right edges are 5 to 14 px narrower than the reference, within its reading uncertainty and inconsistent between screens, so the shared shell was not changed.

## Other measured results (final code)

- Hero text contrast, per text line: worst 5.61:1 (1440 and 1280), 5.82:1 (1920), 7.36:1 (768), 7.65:1 (390); AA needs 4.5:1. A first pass found the header links failing (2.2 to 3.7:1) and the lead paragraph failing at 1440 and 1280; the scrims were adjusted and re-measured.
- Responsive/accessibility: 16 of 16 route/size combinations clean (no overflow, console errors, failed requests, structural problems or invisible focus stops).
- JavaScript on a cold visit: `/` 366.9 kB (116.1 kB gzip), `/sign-in` 478.6 kB, `/dashboard` 370.3 kB, `/classify` 453.8 kB; previously 550.6 kB (171.0 kB gzip) on every route.

## Reproduce

```bash
cd frontend && npm ci && DEV_ALLOWED_HOSTS=.e2b.app npx vite --port 5173      # terminal 1
cd tests/e2e && npm ci
cd visual
export E2E_CHROMIUM_PATH=/path/to/chromium            # and LD_LIBRARY_PATH if it needs bundled libs
node capture.mjs && python compare.py                 # render + compare (needs pillow numpy scikit-image)
node responsive-check.mjs                             # overflow, console, structure, focus at 4 sizes
node contrast-hero.mjs && python contrast_hero.py     # hero text contrast
# production build payload per route:
cd ../../../frontend && npm run build && npx vite preview --port 4173 &
cd ../tests/e2e/visual && node route-payload.mjs
```
