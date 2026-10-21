// Developer tooling (not CI): signs in through the real UI as the demo administrator and captures
// each authenticated screen listed in auth-targets.json to ./out/<id>@auth-${want}.png.
// Needs the demo stack (see README.md) seeded with clearly labelled demonstration records.
import { chromium } from 'playwright-core';
import { readFileSync, mkdirSync } from 'node:fs';

const base = process.env.VISUAL_BASE_URL ?? 'http://127.0.0.1:5173';
const exe = process.env.E2E_CHROMIUM_PATH ?? '/tmp/chromium';
const email = process.env.DEMO_EMAIL ?? 'admin@example.org';
const password = process.env.DEMO_PASSWORD;
if (!password) throw new Error('Set DEMO_PASSWORD to the demo account password');
const theme = process.env.VISUAL_THEME ?? 'light'; // references 05-22 are light screens
const cfg = JSON.parse(readFileSync(new URL('./auth-targets.json', import.meta.url), 'utf8'));
const outDir = new URL('./out/', import.meta.url).pathname;
mkdirSync(outDir, { recursive: true });
const wanted = process.argv.slice(2);
// PNG width and height are the two big-endian integers at byte 16 of the file.
const sizeOf = (ref) => {
  const header = readFileSync(new URL(`../../../docs/ui/reference/${ref}`, import.meta.url));
  return [header.readUInt32BE(16), header.readUInt32BE(20)];
};

const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox', '--font-render-hinting=none'] });
const ctx = await browser.newContext({ viewport: { width: cfg.width, height: 900 }, reducedMotion: 'reduce', colorScheme: 'dark' });
const page = await ctx.newPage();
await page.goto(`${base}/sign-in`, { waitUntil: 'networkidle' });
await page.locator('.auth-card input[type=email]').fill(email);
await page.locator(".auth-card input[autocomplete='current-password']").fill(password);
await page.locator('.auth-card form button[type=submit]').click();
await page.waitForURL(/dashboard/, { timeout: 15000 });

for (const t of cfg.targets) {
  if (wanted.length && !wanted.includes(t.id)) continue;
  const [rw, rh] = sizeOf(t.reference);
  const want = t.theme ?? theme;
  await page.evaluate((th) => window.localStorage.setItem('ecomind.theme', th), want);
  await page.reload({ waitUntil: 'networkidle' });
  const scale = (rw - 2 * cfg.frameInset) / cfg.width;
  const height = Math.round((rh - 2 * cfg.frameInset) / scale);
  await page.setViewportSize({ width: cfg.width, height });
  // client-side navigation keeps the in-memory access token
  await page.evaluate((p) => { window.history.pushState({}, '', p); window.dispatchEvent(new PopStateEvent('popstate')); }, t.path);
  await page.waitForLoadState('networkidle');
  if (t.pick) {
    const sel = page.locator('select').nth(t.pick.select);
    const value = await sel.locator('option', { hasText: t.pick.text }).first().getAttribute('value');
    await sel.selectOption(value);
    await page.waitForTimeout(2000);
    await page.waitForLoadState('networkidle');
    await page.waitForLoadState('networkidle');
  }
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${outDir}${t.id}@auth-${want}.png` });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  const heading = await page.locator('h1').first().textContent().catch(() => null);
  console.log(`${t.id}: ${cfg.width}x${height} h1=${JSON.stringify(heading)} h-overflow=${overflow}px url=${page.url().replace(base, '')}`);
}
await browser.close();
