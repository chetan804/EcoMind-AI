// Visual-iteration helper (developer tooling, not part of the product or CI).
// Usage: node capture.mjs [targetId ...] [--widths=1440,1280,768,390]
// Renders each target from targets.json with a real Chromium and writes screenshots and landmark
// rectangles to ./out/. Compare them to the reference crops with compare.py.
import { chromium } from 'playwright-core';
import { readFileSync, mkdirSync, writeFileSync } from 'node:fs';

const base = process.env.VISUAL_BASE_URL ?? 'http://127.0.0.1:5173';
const exe = process.env.E2E_CHROMIUM_PATH ?? '/tmp/chromium';
const cfg = JSON.parse(readFileSync(new URL('./targets.json', import.meta.url), 'utf8'));
const args = process.argv.slice(2);
const wanted = args.filter((a) => !a.startsWith('--'));
const widthsArg = args.find((a) => a.startsWith('--widths='));
const extraWidths = widthsArg ? widthsArg.slice(9).split(',').map(Number) : [];
const outDir = new URL('./out/', import.meta.url).pathname;
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({
  executablePath: exe,
  args: ['--no-sandbox', '--font-render-hinting=none'],
});

async function shoot(target, width, label, responsive = false) {
  const refPng = target.reference;
  const inset = cfg.frameInset;
  // Reference size is read by compare.py; here we only need the aspect, passed via targets.refSize.
  const [rw, rh] = target.refSize;
  const scale = (rw - 2 * inset) / width;
  const height = responsive ? 900 : (target.height ?? Math.round((rh - 2 * inset) / scale));
  const ctx = await browser.newContext({
    viewport: { width: target.clipSelector ? 1440 : width, height: target.clipSelector ? 1000 : height },
    deviceScaleFactor: 1,
    reducedMotion: 'reduce',
    colorScheme: target.theme === 'light' ? 'light' : 'dark',
  });
  const page = await ctx.newPage();
  await page.goto(base + target.path, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  for (const a of target.actions ?? []) {
    if (a.click) await page.getByRole(a.click.replace(/^role=/, '').split('[')[0]).first().click();
  }
  await page.waitForTimeout(150);
  const name = `${target.id}@${label}`;
  let clip;
  if (target.clipSelector) {
    const b = await page.locator(target.clipSelector).first().boundingBox();
    clip = { x: b.x, y: b.y, width, height };
    await page.screenshot({ path: `${outDir}${name}.png`, clip });
  } else {
    await page.screenshot({ path: `${outDir}${name}.png`, fullPage: responsive });
  }
  const origin = clip ? { x: clip.x, y: clip.y } : { x: 0, y: 0 };
  const rects = {};
  for (const l of target.landmarks ?? []) {
    const b = await page.locator(l.selector).first().boundingBox().catch(() => null);
    rects[l.name] = b ? [b.x - origin.x, b.y - origin.y, b.x - origin.x + b.width, b.y - origin.y + b.height] : null;
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  writeFileSync(`${outDir}${name}.json`, JSON.stringify({ target: target.id, width, height, scale, rects, horizontalOverflowPx: overflow, reference: refPng }, null, 2));
  await ctx.close();
  return { name, overflow };
}

for (const t of cfg.targets) {
  if (wanted.length && !wanted.includes(t.id)) continue;
  const res = [await shoot(t, t.width, 'ref')];
  for (const w of extraWidths) res.push(await shoot({ ...t, clipSelector: undefined, landmarks: [] }, w, String(w), true));
  console.log(res.map((r) => `${r.name} (h-overflow ${r.overflow}px)`).join('\n'));
}
await browser.close();
