// Developer tooling (not CI): builds a small, clearly synthetic scenario through the real API in a
// throw-away database, then captures the map-bearing screens in a real browser.
//
//   Needs: backend + frontend running (see README.md), an administrator account, E2E_CHROMIUM_PATH.
//   ADMIN_EMAIL / ADMIN_PASSWORD  an administrator of that stack
//   VISUAL_BASE_URL               frontend origin (default http://127.0.0.1:5173)
//   MAPS_OUT                      output directory (default ./out/maps)
//
// With no VITE_GOOGLE_MAPS_API_KEY at build time (or no route to Google) the screens show the
// labelled list view, and that is what gets captured. Nothing is drawn by this script.
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';

const base = process.env.VISUAL_BASE_URL ?? 'http://127.0.0.1:5173';
const exe = process.env.E2E_CHROMIUM_PATH ?? '/tmp/chromium';
const adminEmail = process.env.ADMIN_EMAIL;
const adminPassword = process.env.ADMIN_PASSWORD;
if (!adminEmail || !adminPassword) throw new Error('Set ADMIN_EMAIL and ADMIN_PASSWORD');
const out = process.env.MAPS_OUT ?? new URL('./out/maps/', import.meta.url).pathname;
mkdirSync(out, { recursive: true });
const run = Date.now().toString(36).toUpperCase();
const PASSWORD = 'maps capture passphrase 2026';

const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox', '--font-render-hinting=none'] });
const api = (await import('playwright-core')).request;
const http = await api.newContext({ baseURL: base });
const call = async (method, path, token, data) => {
  const res = await http.fetch(`/api/v1${path}`, { method, headers: token ? { Authorization: `Bearer ${token}` } : {}, data });
  if (!res.ok()) throw new Error(`${method} ${path} -> ${res.status()} ${await res.text()}`);
  return res.status() === 204 ? null : res.json();
};
const login = async (email, password) => (await call('POST', '/auth/login', null, { email, password })).access_token;
const admin = await login(adminEmail, adminPassword);

// Synthetic scenario (Hyderabad coordinates; all names start with "Demo").
const collectorEmail = `demo.collector.${run.toLowerCase()}@example.org`;
const collector = await call('POST', '/auth/register', null, { email: collectorEmail, password: PASSWORD, full_name: `Demo Collector ${run}` });
const collectorId = (await call('POST', '/auth/login', null, { email: collectorEmail, password: PASSWORD })).user.id;
await call('PUT', `/admin/users/${collectorId}/roles`, admin, { roles: ['collector'], reason: 'Demonstration account' });
const collectorToken = await login(collectorEmail, PASSWORD);

const zone = await call('POST', '/zones', admin, { code: `DZ-${run}`, name: `Demo zone ${run}`, zone_type: 'mixed_use' });
const depot = await call('POST', '/facilities', admin, { code: `DD-${run}`, name: `Demo depot ${run}`, facility_type: 'depot', latitude: '17.4399', longitude: '78.4983', city: 'Hyderabad', zone_id: zone.id });
await call('POST', '/facilities', admin, { code: `DP-${run}`, name: `Demo processing centre ${run}`, facility_type: 'processing_center', latitude: '17.3616', longitude: '78.4747', city: 'Hyderabad', zone_id: zone.id });
const vehicleA = await call('POST', '/fleet/vehicles', admin, { registration_number: `DEMO-A-${run}`, vehicle_type: 'van', capacity_kg: '900', home_facility_id: depot.id });
const vehicleB = await call('POST', '/fleet/vehicles', admin, { registration_number: `DEMO-B-${run}`, vehicle_type: 'van', capacity_kg: '900' });
await call('POST', '/fleet/vehicles', admin, { registration_number: `DEMO-C-${run}`, vehicle_type: 'van', capacity_kg: '900' });
const stops = [['Demo stop Banjara Hills', '17.4126', '78.4482'], ['Demo stop Charminar', '17.3616', '78.4747'], ['Demo stop Hitech City', '17.4435', '78.3772']];
const taskIds = [];
for (const [title, lat, lng] of stops) {
  const t = await call('POST', '/collection/tasks', admin, { title: `${title} ${run}`, latitude: lat, longitude: lng, priority: 'normal' });
  taskIds.push(t.id);
}
await call('POST', `/collection/tasks/${taskIds[0]}/assign`, admin, { assignee_id: collectorId, vehicle_id: vehicleA.id });
const plan = await call('POST', '/route-planning/plans', admin, {
  name: `Demo route ${run}`, planned_date: new Date(Date.now() + 86_400_000).toISOString().slice(0, 10), start_facility_id: depot.id, task_ids: taskIds, vehicle_id: vehicleB.id,
});
// Real source (collector's own report) for vehicle A; simulator (separate endpoint) for vehicle B.
await call('POST', `/collection/tasks/${taskIds[0]}/start`, collectorToken, {});
const now = Date.now();
for (const [i, [lat, lng]] of [['17.4300', '78.4900'], ['17.4200', '78.4700'], ['17.4130', '78.4490']].entries()) {
  await call('POST', `/tracking/vehicles/${vehicleA.id}/locations`, collectorToken, {
    latitude: lat, longitude: lng, source: 'mobile_client', recorded_at: new Date(now - (3 - i) * 20_000).toISOString(), collection_task_id: taskIds[0],
  });
}
for (const [lat, lng] of [['17.4399', '78.4983'], ['17.4300', '78.4800']]) {
  await call('POST', `/tracking/simulation/vehicles/${vehicleB.id}/locations`, admin, { latitude: lat, longitude: lng, route_plan_id: plan.id });
}

const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
const page = await ctx.newPage();
await page.goto(`${base}/sign-in`, { waitUntil: 'networkidle' });
await page.locator('.auth-card input[type=email]').fill(adminEmail);
await page.locator(".auth-card input[autocomplete='current-password']").fill(adminPassword);
await page.locator('.auth-card form button[type=submit]').click();
await page.waitForURL(/dashboard/, { timeout: 15000 });
const go = async (path) => {
  await page.evaluate((p) => { window.history.pushState({}, '', p); window.dispatchEvent(new PopStateEvent('popstate')); }, path);
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(600);
};
const shot = async (name, locator) => {
  const target = locator ?? page;
  await target.screenshot({ path: `${out}/${name}.png`, ...(locator ? {} : { fullPage: true }) });
  console.log('captured', name);
};

await go('/dashboard');
await page.getByRole('region', { name: /Fleet positions/ }).first().waitFor();
await shot('command-center');

await go('/fleet');
await page.getByLabel('Search').fill(run);
await page.waitForTimeout(800);
await shot('fleet');

await go('/collection');
await page.getByRole('button', { name: new RegExp(`Open task: Demo stop Banjara Hills ${run}`) }).click();
await page.getByRole('region', { name: 'Location and tracking' }).waitFor();
await page.waitForTimeout(800);
await shot('collection-tracking', page.getByRole('dialog', { name: 'Collection task' }));

await go('/routes');
await page.getByRole('button', { name: new RegExp(`Demo route ${run}`) }).click();
await page.getByRole('dialog', { name: 'Route plan' }).getByText(/No road route|Road route/).first().waitFor();
await page.waitForTimeout(800);
await shot('route-optimization', page.getByRole('dialog', { name: 'Route plan' }));

await go('/locations');
await page.getByLabel('Search').first().fill(run).catch(() => undefined);
await page.waitForTimeout(800);
await page.getByRole('button', { name: new RegExp(`Show facilities in Demo zone ${run}`) }).click();
await page.getByRole('table', { name: `Facilities in Demo zone ${run}`, exact: true }).waitFor();
await page.waitForTimeout(500);
await shot('locations-zones');

await browser.close();
