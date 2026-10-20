// Real-browser checks for the four implemented screens across viewport sizes:
// horizontal overflow, console errors/warnings, page errors, failed requests, basic
// accessibility structure (lang, one <main>, one <h1>, unnamed controls, unlabeled inputs)
// and keyboard focus visibility. Also writes a screenshot per route and size to out/responsive/.
// Usage: E2E_CHROMIUM_PATH=... node responsive-check.mjs [baseURL]
import { mkdirSync } from 'node:fs';
import { chromium } from 'playwright-core';

const base = process.argv[2] ?? 'http://localhost:5173';
const outDir = new URL('./out/responsive/', import.meta.url).pathname;
mkdirSync(outDir, { recursive: true });
const sizes = [[1440, 900], [1280, 800], [768, 1024], [390, 844]];
const routes = [['landing', '/'], ['sign-in', '/sign-in'], ['dashboard', '/dashboard'], ['classify', '/classify']];
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_PATH, args: ['--no-sandbox'] });
let problems = 0;

for (const [w, h] of sizes) {
  for (const [name, path] of routes) {
    const page = await browser.newPage({ viewport: { width: w, height: h } });
    const issues = [];
    page.on('console', (m) => { if (['error', 'warning'].includes(m.type())) issues.push(`console.${m.type()}: ${m.text().slice(0, 140)}`); });
    page.on('pageerror', (e) => issues.push(`pageerror: ${e.message.slice(0, 140)}`));
    page.on('requestfailed', (r) => issues.push(`requestfailed: ${r.url().slice(0, 100)}`));
    await page.goto(base + path, { waitUntil: 'networkidle' });

    const dom = await page.evaluate(() => {
      const unnamed = [...document.querySelectorAll('button, a[href], [role=button]')].filter((el) => !(el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.textContent.trim() || el.querySelector('img[alt]:not([alt=""])') || el.getAttribute('title'))).length;
      // Elements that are not rendered (display: none, hidden) are not in the accessibility tree.
      const unlabeled = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')].filter((el) => el.checkVisibility() && !(el.labels?.length || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby'))).length;
      return {
        lang: document.documentElement.lang,
        mains: document.querySelectorAll('main').length,
        h1: document.querySelectorAll('h1').length,
        unnamed, unlabeled,
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });

    let invisibleFocus = 0;
    let stops = 0;
    for (let i = 0; i < 14; i += 1) {
      await page.keyboard.press('Tab');
      const ok = await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        const cs = getComputedStyle(el);
        return (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none';
      });
      if (ok === null) continue;
      stops += 1;
      if (!ok) invisibleFocus += 1;
    }

    if (dom.overflow > 0) issues.push(`horizontal overflow ${dom.overflow}px`);
    if (!dom.lang) issues.push('missing <html lang>');
    if (dom.mains !== 1) issues.push(`<main> count ${dom.mains}`);
    if (dom.h1 !== 1) issues.push(`<h1> count ${dom.h1}`);
    if (dom.unnamed) issues.push(`${dom.unnamed} controls without an accessible name`);
    if (dom.unlabeled) issues.push(`${dom.unlabeled} inputs without a label`);
    if (invisibleFocus) issues.push(`${invisibleFocus}/${stops} focus stops with no visible focus style`);

    await page.screenshot({ path: `${outDir}${name}-${w}.png`, fullPage: false });
    console.log(`${String(w).padStart(4)}x${String(h).padEnd(4)} ${name.padEnd(10)} ${issues.length ? 'ISSUES: ' + issues.join(' | ') : `ok (overflow ${dom.overflow}px, ${stops} focus stops visible)`}`);
    problems += issues.length;
    await page.close();
  }
}
await browser.close();
console.log(problems ? `\n${problems} issue(s)` : '\nno issues');
process.exit(problems ? 1 : 0);
