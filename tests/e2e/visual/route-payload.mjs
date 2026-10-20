// Reports the JavaScript a cold visit to each route downloads (raw and gzip), using a real
// browser against a running server (use `vite preview` on a production build).
// Usage: E2E_CHROMIUM_PATH=... node route-payload.mjs [baseURL]
import { gzipSync } from 'node:zlib';
import { chromium } from 'playwright-core';

const base = process.argv[2] ?? 'http://localhost:4173';
const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM_PATH, args: ['--no-sandbox'] });
for (const route of ['/', '/sign-in', '/dashboard', '/classify']) {
  const page = await browser.newPage();
  let raw = 0;
  let gz = 0;
  let files = 0;
  page.on('response', async (res) => {
    if (res.request().resourceType() !== 'script') return;
    const body = await res.body().catch(() => null);
    if (!body) return;
    raw += body.length;
    gz += gzipSync(body).length;
    files += 1;
  });
  await page.goto(base + route, { waitUntil: 'networkidle' });
  console.log(`${route.padEnd(11)} ${String(files).padStart(2)} scripts  ${(raw / 1024).toFixed(1).padStart(6)} kB raw  ${(gz / 1024).toFixed(1).padStart(6)} kB gzip`);
  await page.close();
}
await browser.close();
