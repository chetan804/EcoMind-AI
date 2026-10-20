# Visual iteration tooling

Developer tooling for comparing the built screens with the design references. It is **not** part of the product, not run in CI, and does not gate merges. The reference PNGs in `docs/ui/reference/` (with their `manifest.json`) are crops of one blurry AI-generated composite, so these numbers guide iteration; they are not an acceptance test and nothing here claims pixel accuracy.

## How it works

1. `capture.mjs` renders each target in `targets.json` with a real Chromium (`playwright-core`, already installed by `tests/e2e`). The viewport width is the design width; the height is derived from the reference's proportions. It writes a screenshot and the DOM rectangle of each landmark to `out/` (git-ignored). `--widths=1280,768,390` additionally captures full pages at those widths and reports horizontal overflow.
2. `compare.py` downscales the screenshot to the **reference's own pixel size** (the reference is never enlarged), ignores the reference's 3 px showcase frame, and prints landmark deltas in design pixels (positive = further right / lower / larger), SSIM, mean colour error and a coarse colour-grid distance. It also writes `out/<id>@sidebyside.png` (reference left, render right) and `out/<id>@diff.png`.

Landmark boxes in `targets.json` were read by eye from the blurry references: expect about +/-5 design px of reading error.

## Other checks in this folder

- `responsive-check.mjs`: overflow, console errors, failed requests, landmarks, names and focus visibility on the four screens at 1440, 1280, 768 and 390 px.
- `contrast-hero.mjs` + `contrast_hero.py`: per-line WCAG contrast of the landing hero text over the artwork.
- `route-payload.mjs`: JavaScript downloaded by a cold visit to each route (use `vite preview` on a production build).

Committed results live in `docs/ui/evidence/`.

## Run it

```bash
cd frontend && DEV_ALLOWED_HOSTS=.e2b.app npx vite --port 5173      # in one terminal
cd tests/e2e/visual
E2E_CHROMIUM_PATH=/path/to/chromium node capture.mjs [targetId ...] [--widths=1280,768,390]
python compare.py [targetId ...]        # needs: pip install pillow numpy scikit-image
```

`VISUAL_BASE_URL` overrides the default `http://127.0.0.1:5173`. If Chromium needs bundled libraries, set `LD_LIBRARY_PATH` as for the Playwright e2e tests.

## Note on super-resolved references

A generative 4x upscale of the references was used as a viewing aid only. It invents detail and text, so it is not a source for copy, numbers or colours, and the outputs are not committed.
