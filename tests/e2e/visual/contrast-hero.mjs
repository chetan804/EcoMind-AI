// Step 1 of the hero contrast check: hides the foreground content, screenshots the artwork and
// records every text box with its colour. `contrast_hero.py` then samples the brightest 5% of
// background pixels under each box (the worst case for light text on a dark scrim).
// Usage: E2E_CHROMIUM_PATH=... node contrast-hero.mjs [baseURL] && python contrast_hero.py
import { mkdirSync, writeFileSync } from 'node:fs';
import { chromium } from 'playwright-core';

const outDir = new URL('./out', import.meta.url).pathname;
mkdirSync(outDir, { recursive: true });

const base = process.argv[2] ?? 'http://localhost:5173';
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_PATH, args: ['--no-sandbox'] });

for (const [w, h] of [[1440, 900], [1280, 800], [1920, 1080], [768, 1024], [390, 844]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  await page.goto(`${base}/`, { waitUntil: 'networkidle' });
  const items = await page.evaluate(() => {
    const sel = '.landing__top h1, .landing__top h1 span, .landing__top p, .landing__top a, .landing__top button, .landing__top nav a, .landing__top dd, .landing__top dt, .landing__top li';
    const out = [];
    for (const el of document.querySelectorAll(sel)) {
      const cs = getComputedStyle(el);
      for (const node of el.childNodes) {
        if (node.nodeType !== 3 || !node.textContent.trim()) continue;
        const range = document.createRange();
        range.selectNodeContents(node);
        for (const r of range.getClientRects()) {
          if (r.width < 1 || r.height < 1 || r.y + scrollY > 1100) continue;
          out.push({ name: node.textContent.trim().slice(0, 28), x: r.x, y: r.y + scrollY, w: r.width, h: r.height, color: cs.color, size: parseFloat(cs.fontSize), bg: cs.backgroundColor });
        }
      }
    }
    return out;
  });
  await page.addStyleTag({ content: '.landing__top > *:not(.hero-art){visibility:hidden !important} .landing__top *:not(.hero-art):not(.hero-art *){visibility:hidden !important}' });
  await page.screenshot({ path: `${outDir}/hero-bg-${w}.png`, fullPage: true });
  writeFileSync(`${outDir}/hero-text-${w}.json`, JSON.stringify(items));
  console.log(`${w}x${h}: captured ${items.length} text boxes`);
  await page.close();
}
await browser.close();
