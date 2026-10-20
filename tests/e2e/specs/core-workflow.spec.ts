import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { SESSION_HINT_KEY } from './fixtures';

/**
 * Core operational workflow in a real browser against the real stack, no stubbing:
 *
 *   citizen reports waste -> manager verifies it and turns it into a task, assigns a collector and
 *   a vehicle -> collector starts it and completes it with a weight -> the weight is stored, the
 *   reporter's reward follows from the rule, and analytics read the new weight back from the
 *   database, still correct after a reload.
 *
 * Accounts are created through the real API. Roles can only be granted by an administrator, so the
 * stack needs one: set E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD (CI creates it with
 * `python -m app.cli create-admin`). Without them this spec FAILS rather than skips, because a
 * skipped core workflow is not a pass.
 */
const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const PASSWORD = 'e2e test passphrase 2026'; // throw-away database only
const WEIGHT_KG = 42.5;

interface Actor {
  email: string;
  id: string;
  token: string;
}

async function signUp(api: APIRequestContext, email: string, name: string): Promise<Actor> {
  const created = await api.post('/api/v1/auth/register', { data: { email, password: PASSWORD, full_name: name } });
  expect(created.ok(), `register ${email}`).toBe(true);
  const login = await api.post('/api/v1/auth/login', { data: { email, password: PASSWORD } });
  expect(login.ok(), `login ${email}`).toBe(true);
  const body = (await login.json()) as { access_token: string; user: { id: string } };
  return { email, id: body.user.id, token: body.access_token };
}

async function pageFor(browser: Browser, email: string, password = PASSWORD): Promise<Page> {
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  // Real sign-in: the HttpOnly refresh cookie lands in this context, as after using the form.
  const response = await page.request.post('/api/v1/auth/login', { data: { email, password } });
  expect(response.ok(), `sign in ${email}`).toBe(true);
  await page.addInitScript((key) => window.localStorage.setItem(key, '1'), SESSION_HINT_KEY);
  return page;
}

test('report to collected weight, reward and analytics', async ({ browser, playwright }) => {
  expect(adminEmail && adminPassword, 'E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD must be set for the core workflow').toBeTruthy();
  const run = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  const title = `E2E dumped sofa ${run}`;
  const registration = `E2E-${run.toUpperCase()}`;

  const api = await playwright.request.newContext({ baseURL });
  const citizen = await signUp(api, `citizen.${run}@example.org`, 'Casey Citizen');
  const manager = await signUp(api, `manager.${run}@example.org`, 'Morgan Manager');
  const collector = await signUp(api, `collector.${run}@example.org`, `Colby Collector ${run}`);

  // Roles come from an administrator through the real administration API.
  const adminLogin = await api.post('/api/v1/auth/login', { data: { email: adminEmail, password: adminPassword } });
  expect(adminLogin.ok(), 'administrator sign-in').toBe(true);
  const adminToken = ((await adminLogin.json()) as { access_token: string }).access_token;
  for (const [user, role] of [[manager, 'manager'], [collector, 'collector']] as const) {
    const res = await api.put(`/api/v1/admin/users/${user.id}/roles`, {
      headers: { Authorization: `Bearer ${adminToken}` },
      data: { roles: [role], reason: 'End-to-end test account' },
    });
    expect(res.ok(), `grant ${role}`).toBe(true);
  }
  // A role change applies to tokens issued afterwards, so sign in again for the API calls below.
  const managerLogin = await api.post('/api/v1/auth/login', { data: { email: manager.email, password: PASSWORD } });
  manager.token = ((await managerLogin.json()) as { access_token: string }).access_token;
  const managerHeaders = { Authorization: `Bearer ${manager.token}` };

  const vehicle = await api.post('/api/v1/fleet/vehicles', {
    headers: managerHeaders,
    data: { registration_number: registration, vehicle_type: 'van', capacity_kg: '900' },
  });
  expect(vehicle.ok(), 'create vehicle').toBe(true);

  const before = await api.get('/api/v1/analytics/overview', { headers: managerHeaders });
  const totalBefore = Number(((await before.json()) as { collection: { collected_weight_kg_total: string } }).collection.collected_weight_kg_total);

  // 1. The citizen files a report through the form.
  const citizenPage = await pageFor(browser, citizen.email);
  await citizenPage.goto('/reports');
  await citizenPage.getByRole('button', { name: 'Report waste' }).click();
  const reportDialog = citizenPage.getByRole('dialog', { name: 'Report waste' });
  await reportDialog.getByLabel('Title').fill(title);
  await reportDialog.getByLabel('Address or landmark').fill('Plot 12, Test Road');
  await reportDialog.getByLabel(/Estimated weight/).fill('40');
  await reportDialog.getByRole('button', { name: 'Submit report' }).click();
  await expect(citizenPage.getByRole('button', { name: `Open report: ${title}` })).toBeVisible();

  // 2. The manager verifies it and creates the task from it.
  const managerPage = await pageFor(browser, manager.email);
  await managerPage.goto('/reports');
  await managerPage.getByLabel('Search').fill(run);
  await managerPage.getByRole('button', { name: `Open report: ${title}` }).click();
  await managerPage.getByRole('button', { name: 'Review report' }).click();
  await managerPage.getByRole('dialog', { name: 'Review report' }).getByRole('button', { name: 'Save review' }).click();
  await managerPage.getByRole('button', { name: 'Create collection task' }).click();
  await managerPage.getByRole('dialog', { name: 'New collection task' }).getByRole('button', { name: 'Create task' }).click();

  // 3. The manager assigns the collector and the vehicle.
  await managerPage.goto('/collection');
  await managerPage.getByRole('button', { name: `Open task: ${title}` }).click();
  await managerPage.getByRole('button', { name: 'Assign', exact: true }).click();
  const assign = managerPage.getByRole('dialog', { name: `Assign: ${title}` });
  await assign.getByLabel('Collector').selectOption({ label: `Colby Collector ${run}` });
  const vehicleSelect = assign.getByLabel('Vehicle (optional)');
  const vehicleValue = await vehicleSelect.locator('option', { hasText: registration }).getAttribute('value');
  expect(vehicleValue, 'the new vehicle is offered').toBeTruthy();
  await vehicleSelect.selectOption(vehicleValue as string);
  await assign.getByRole('button', { name: 'Assign', exact: true }).click();
  await expect(managerPage.getByRole('dialog', { name: 'Collection task' }).locator('.badge', { hasText: 'Assigned' })).toBeVisible();

  // 4. The collector works the task and records the weight.
  const collectorPage = await pageFor(browser, collector.email);
  await collectorPage.goto('/collection');
  await collectorPage.getByRole('button', { name: `Open task: ${title}` }).click();
  await collectorPage.getByRole('button', { name: 'Start task' }).click();
  await collectorPage.getByRole('button', { name: 'Complete with weight' }).click();
  const complete = collectorPage.getByRole('dialog', { name: 'Complete task' });
  await complete.getByLabel('Collected weight (kg)').fill(String(WEIGHT_KG));
  await complete.getByRole('button', { name: 'Complete task' }).click();
  await expect(collectorPage.getByRole('dialog', { name: 'Collection task' }).locator('.badge', { hasText: 'Completed' })).toBeVisible();

  // 5. The reporter's reward follows from the rule (points per kg, default 10), after a reload.
  await citizenPage.goto('/rewards');
  await expect(citizenPage.getByText('Points balance')).toBeVisible();
  const balance = await api.get('/api/v1/rewards/me/balance', { headers: { Authorization: `Bearer ${citizen.token}` } });
  const { points } = (await balance.json()) as { points: number };
  expect(points).toBe(Math.round(WEIGHT_KG * 10));
  await citizenPage.reload();
  await expect(citizenPage.getByText(String(points)).first()).toBeVisible();

  // 6. Analytics read the stored weight from the database, and still do after a reload.
  const after = await api.get('/api/v1/analytics/overview', { headers: managerHeaders });
  const totalAfter = Number(((await after.json()) as { collection: { collected_weight_kg_total: string } }).collection.collected_weight_kg_total);
  expect(totalAfter - totalBefore).toBeCloseTo(WEIGHT_KG, 3);
  await managerPage.goto('/analytics');
  await managerPage.reload();
  await expect(managerPage.getByRole('heading', { level: 1, name: 'Executive analytics' })).toBeVisible();

  await api.dispose();
});
