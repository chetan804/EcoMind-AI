import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { E2E_EMAIL, E2E_PASSWORD, SESSION_HINT_KEY } from './fixtures';

/**
 * Vehicle and collection tracking in a real browser against the real stack, no stubbing:
 *
 *   a collector starts an assigned task and shares the device position through the browser's own
 *   Geolocation API -> the manager sees that vehicle as LIVE GPS on the fleet screen and in the
 *   collection task, while a vehicle that never reported stays LOCATION UNAVAILABLE.
 *   An older report is kept as out-of-order and never replaces the latest position. Simulator data
 *   is accepted only through its own endpoint, is labelled SIMULATED, and never becomes a
 *   vehicle's real position. People without the right permission are refused.
 *
 * The default map is the built-in offline one (no key). In CI it either draws with WebGL or, if the
 * browser has none, shows the labelled list of the same data; both are accepted and the same table
 * is asserted either way. Drawing on Google's map needs a key and is verified manually; see
 * docs/maps/GOOGLE_MAPS_INTEGRATION.md. Drawing on real tiles needs a tile file (docs/maps/OFFLINE_MAPS.md).
 *
 * Needs E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD (like core-workflow.spec.ts) and fails without them.
 * The administrator acts as the fleet manager and the shared e2e account is the no-role citizen, so
 * only ONE account is registered here: the stack allows ten registrations per address per hour and
 * the whole e2e suite shares that budget.
 */
const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const PASSWORD = 'e2e test passphrase 2026'; // throw-away database only

interface Actor {
  email: string;
  id: string;
  token: string;
}
const bearer = (a: Actor) => ({ Authorization: `Bearer ${a.token}` });

/** Interactive map: open the list disclosure. No WebGL: the list is already the map area. */
async function showLocationList(page: Page): Promise<void> {
  const disclosure = page.getByText('Show these locations as a list').first();
  const noWebgl = page.getByText(/Map not available: this browser cannot draw the map/).first();
  await expect(disclosure.or(noWebgl)).toBeVisible();
  if (await disclosure.isVisible()) {
    const opened = await page.locator('details').filter({ has: disclosure }).first().evaluate((el) => (el as HTMLDetailsElement).open);
    if (!opened) await disclosure.click();
  }
}

async function signUp(api: APIRequestContext, email: string, name: string): Promise<Actor> {
  const created = await api.post('/api/v1/auth/register', { data: { email, password: PASSWORD, full_name: name } });
  expect(created.ok(), `register ${email}`).toBe(true);
  return signIn(api, email);
}
async function signIn(api: APIRequestContext, email: string, password = PASSWORD): Promise<Actor> {
  const login = await api.post('/api/v1/auth/login', { data: { email, password } });
  expect(login.ok(), `login ${email}`).toBe(true);
  const body = (await login.json()) as { access_token: string; user: { id: string } };
  return { email, id: body.user.id, token: body.access_token };
}
async function pageFor(browser: Browser, email: string, options: Parameters<Browser['newContext']>[0] = {}, password = PASSWORD): Promise<Page> {
  const context = await browser.newContext({ baseURL, ...options });
  const page = await context.newPage();
  const response = await page.request.post('/api/v1/auth/login', { data: { email, password } });
  expect(response.ok(), `sign in ${email}`).toBe(true);
  await page.addInitScript((key) => window.localStorage.setItem(key, '1'), SESSION_HINT_KEY);
  return page;
}

test('collector shares a real position; the fleet shows LIVE GPS, never-reported vehicles stay unavailable, simulation stays separate', async ({ browser, playwright }) => {
  expect(adminEmail && adminPassword, 'E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD must be set').toBeTruthy();
  const run = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  const regA = `TRK-A-${run.toUpperCase()}`;
  const regB = `TRK-B-${run.toUpperCase()}`;
  const title = `E2E tracked pickup ${run}`;
  const api = await playwright.request.newContext({ baseURL });

  const collector = await signUp(api, `trk.collector.${run}@example.org`, `Colby Collector ${run}`);
  const admin = await signIn(api, adminEmail as string, adminPassword);
  const granted = await api.put(`/api/v1/admin/users/${collector.id}/roles`, { headers: bearer(admin), data: { roles: ['collector'], reason: 'End-to-end test account' } });
  expect(granted.ok(), 'grant collector').toBe(true);
  const c = await signIn(api, collector.email);
  const m = admin; // the administrator holds every fleet permission, including fleet:manage
  const citizen = await signIn(api, E2E_EMAIL, E2E_PASSWORD);

  const vehicles: Record<string, string> = {};
  for (const reg of [regA, regB]) {
    const res = await api.post('/api/v1/fleet/vehicles', { headers: bearer(m), data: { registration_number: reg, vehicle_type: 'van', capacity_kg: '900' } });
    expect(res.ok(), `create ${reg}`).toBe(true);
    vehicles[reg] = ((await res.json()) as { id: string }).id;
  }
  const task = await api.post('/api/v1/collection/tasks', { headers: bearer(m), data: { title, latitude: '17.385000', longitude: '78.486700', priority: 'normal' } });
  expect(task.ok(), 'create task').toBe(true);
  const taskId = ((await task.json()) as { id: string }).id;
  const assign = await api.post(`/api/v1/collection/tasks/${taskId}/assign`, { headers: bearer(m), data: { assignee_id: c.id, vehicle_id: vehicles[regA] } });
  expect(assign.ok(), 'assign').toBe(true);

  // Nothing has reported yet: both vehicles are LOCATION UNAVAILABLE according to the API.
  const before = (await (await api.get('/api/v1/tracking/vehicles', { headers: bearer(m) })).json()) as { items: { vehicle_id: string; status: string; position: unknown }[] };
  for (const reg of [regA, regB]) {
    const row = before.items.find((i) => i.vehicle_id === vehicles[reg]);
    expect(row?.status, `${reg} before any report`).toBe('unavailable');
    expect(row?.position).toBeNull();
  }

  // 1. The collector starts the task and shares the device position (real browser Geolocation).
  const collectorPage = await pageFor(browser, collector.email, { geolocation: { latitude: 17.3851, longitude: 78.4867, accuracy: 12 }, permissions: ['geolocation'] });
  await collectorPage.goto('/collection');
  await collectorPage.getByRole('button', { name: `Open task: ${title}` }).click();
  await collectorPage.getByRole('button', { name: 'Start task' }).click();
  const share = collectorPage.getByRole('dialog', { name: 'Collection task' });
  await expect(share.getByRole('button', { name: 'Share my position' })).toBeVisible();
  await share.getByRole('button', { name: 'Share my position' }).click();
  await expect(share.getByText(/1 report sent/)).toBeVisible();

  // 2. The API now has a LIVE position from a real source for vehicle A only.
  const after = (await (await api.get('/api/v1/tracking/vehicles', { headers: bearer(m) })).json()) as { items: { vehicle_id: string; status: string; simulated: boolean; position: { source: string; collection_task_id: string | null; latitude: string } | null }[] };
  const rowA = after.items.find((i) => i.vehicle_id === vehicles[regA] && !i.simulated);
  expect(rowA?.status).toBe('live');
  expect(rowA?.position?.source).toBe('mobile_client');
  expect(rowA?.position?.collection_task_id).toBe(taskId);
  expect(Number(rowA?.position?.latitude)).toBeCloseTo(17.3851, 4);
  expect(after.items.find((i) => i.vehicle_id === vehicles[regB])?.status).toBe('unavailable');

  // 3. An older report is kept but never replaces the latest position (out-of-order handling).
  const old = await api.post(`/api/v1/tracking/vehicles/${vehicles[regA]}/locations`, {
    headers: bearer(c),
    data: { latitude: '17.300000', longitude: '78.400000', recorded_at: new Date(Date.now() - 20 * 60_000).toISOString(), source: 'mobile_client' },
  });
  expect(old.status()).toBe(201);
  expect(((await old.json()) as { event: { quality: string } }).event.quality).toBe('out_of_order');
  const latest = (await (await api.get(`/api/v1/tracking/vehicles/${vehicles[regA]}`, { headers: bearer(m) })).json()) as { status: string; position: { latitude: string } }[];
  expect(latest[0]?.status).toBe('live');
  expect(Number(latest[0]?.position.latitude)).toBeCloseTo(17.3851, 4);

  // 4. The manager sees the same facts on screen.
  const managerPage = await pageFor(browser, adminEmail as string, {}, adminPassword);
  await managerPage.goto('/fleet');
  await managerPage.getByLabel('Search').fill(`-${run.toUpperCase()}`);
  const vehicleTable = managerPage.getByRole('table', { name: 'Fleet vehicles' });
  const rowAOnScreen = vehicleTable.getByRole('row').filter({ hasText: regA });
  const rowBOnScreen = vehicleTable.getByRole('row').filter({ hasText: regB });
  await expect(rowAOnScreen.getByText('LIVE GPS', { exact: true })).toBeVisible();
  await expect(rowBOnScreen.getByText('LOCATION UNAVAILABLE', { exact: true })).toBeVisible();
  // Either an interactive map with the list in a disclosure, or (no WebGL) the labelled list itself;
  // never a blank box.
  await showLocationList(managerPage);
  const list = managerPage.getByRole('table', { name: 'Fleet positions: locations' });
  await expect(list.getByRole('rowheader', { name: regA })).toBeVisible();
  await expect(list.getByRole('rowheader', { name: regB })).toHaveCount(0); // never reported: no marker

  await managerPage.goto('/collection');
  await managerPage.getByRole('button', { name: `Open task: ${title}` }).click();
  const detail = managerPage.getByRole('dialog', { name: 'Collection task' });
  await expect(detail.getByRole('region', { name: 'Location and tracking' }).getByText('LIVE GPS').first()).toBeVisible();

  // 5. The simulator is separate: its own endpoint, labelled SIMULATED, never the real position.
  const config = (await (await api.get('/api/v1/tracking/config', { headers: bearer(m) })).json()) as { simulator_enabled: boolean };
  if (config.simulator_enabled) {
    const sim = await api.post(`/api/v1/tracking/simulation/vehicles/${vehicles[regB]}/locations`, { headers: bearer(m), data: { latitude: '17.400000', longitude: '78.500000' } });
    expect(sim.status()).toBe(201);
    const withSim = (await (await api.get('/api/v1/tracking/vehicles?include_simulated=true', { headers: bearer(m) })).json()) as { items: { vehicle_id: string; status: string; simulated: boolean }[] };
    expect(withSim.items.find((i) => i.vehicle_id === vehicles[regB] && i.simulated)?.status).toBe('simulated');
    expect(withSim.items.find((i) => i.vehicle_id === vehicles[regB] && !i.simulated)?.status).toBe('unavailable');
    const history = (await (await api.get(`/api/v1/tracking/vehicles/${vehicles[regB]}/locations`, { headers: bearer(m) })).json()) as { items: unknown[] };
    expect(history.items).toHaveLength(0); // real history is untouched

    await managerPage.goto('/fleet');
    await managerPage.getByLabel('Search').fill(`-${run.toUpperCase()}`);
    await showLocationList(managerPage);
    const simList = managerPage.getByRole('table', { name: 'Fleet positions: locations' });
    await expect(simList.getByRole('rowheader', { name: `${regB} (simulated)` })).toBeVisible();
    await expect(simList.getByRole('row').filter({ hasText: regB }).getByText('SIMULATED', { exact: true })).toBeVisible();
    await expect(managerPage.getByRole('table', { name: 'Fleet vehicles' }).getByRole('row').filter({ hasText: regB }).getByText('LOCATION UNAVAILABLE')).toBeVisible();

    const reset = await api.delete(`/api/v1/tracking/simulation/vehicles/${vehicles[regB]}/locations`, { headers: bearer(m) });
    expect(reset.ok()).toBe(true);
    // The collector may not use the simulator.
    const denied = await api.post(`/api/v1/tracking/simulation/vehicles/${vehicles[regB]}/locations`, { headers: bearer(c), data: { latitude: '17.4', longitude: '78.5' } });
    expect(denied.status()).toBe(403);
  } else {
    const off = await api.post(`/api/v1/tracking/simulation/vehicles/${vehicles[regB]}/locations`, { headers: bearer(m), data: { latitude: '17.4', longitude: '78.5' } });
    expect(off.status()).toBe(404);
  }

  // 6. Validation and authorisation are enforced by the server.
  const asSimulator = await api.post(`/api/v1/tracking/vehicles/${vehicles[regA]}/locations`, {
    headers: bearer(c),
    data: { latitude: '17.4', longitude: '78.5', recorded_at: new Date().toISOString(), source: 'simulator' },
  });
  expect(asSimulator.status()).toBe(422);
  const nullIsland = await api.post(`/api/v1/tracking/vehicles/${vehicles[regA]}/locations`, {
    headers: bearer(c),
    data: { latitude: '0', longitude: '0', recorded_at: new Date().toISOString(), source: 'mobile_client' },
  });
  expect(nullIsland.status()).toBe(422);
  const otherVehicle = await api.post(`/api/v1/tracking/vehicles/${vehicles[regB]}/locations`, {
    headers: bearer(c),
    data: { latitude: '17.4', longitude: '78.5', recorded_at: new Date().toISOString(), source: 'mobile_client' },
  });
  expect(otherVehicle.status()).toBe(403);
  const citizenRead = await api.get('/api/v1/tracking/vehicles', { headers: bearer(citizen) });
  expect(citizenRead.status()).toBe(403);
  const collectorList = (await (await api.get('/api/v1/tracking/vehicles', { headers: bearer(c) })).json()) as { items: { vehicle_id: string }[] };
  expect(collectorList.items.map((i) => i.vehicle_id)).not.toContain(vehicles[regB]); // not their vehicle
});
