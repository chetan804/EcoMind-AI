import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { SESSION_HINT_KEY } from './fixtures';

/**
 * Marketplace journey in a real browser against the real stack, no stubbing:
 *
 *   an operator drafts and publishes a listing -> a citizen finds it and asks for it -> the owner
 *   sees the request and accepts it -> the listing is reserved and the citizen sees the decision,
 *   still true after a reload.
 *
 * Needs E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD (roles are granted by an administrator); without
 * them the spec FAILS rather than skips.
 */
const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const PASSWORD = 'e2e test passphrase 2026'; // throw-away database only

async function signUp(api: APIRequestContext, email: string, name: string): Promise<string> {
  const created = await api.post('/api/v1/auth/register', { data: { email, password: PASSWORD, full_name: name } });
  expect(created.ok(), `register ${email}`).toBe(true);
  const login = await api.post('/api/v1/auth/login', { data: { email, password: PASSWORD } });
  expect(login.ok(), `login ${email}`).toBe(true);
  return ((await login.json()) as { user: { id: string } }).user.id;
}

async function pageFor(browser: Browser, email: string): Promise<Page> {
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  const response = await page.request.post('/api/v1/auth/login', { data: { email, password: PASSWORD } });
  expect(response.ok(), `sign in ${email}`).toBe(true);
  await page.addInitScript((key) => window.localStorage.setItem(key, '1'), SESSION_HINT_KEY);
  return page;
}

test('offer, request, accept and reserve a surplus listing', async ({ browser, playwright }) => {
  expect(adminEmail && adminPassword, 'E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD must be set').toBeTruthy();
  const run = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  const title = `E2E office chairs ${run}`;
  const api = await playwright.request.newContext({ baseURL });
  const operatorEmail = `operator.${run}@example.org`;
  const citizenEmail = `citizen.${run}@example.org`;
  const operatorId = await signUp(api, operatorEmail, `Olive Operator ${run}`);
  await signUp(api, citizenEmail, `Casey Citizen ${run}`);

  const adminLogin = await api.post('/api/v1/auth/login', { data: { email: adminEmail, password: adminPassword } });
  expect(adminLogin.ok(), 'administrator sign-in').toBe(true);
  const adminToken = ((await adminLogin.json()) as { access_token: string }).access_token;
  const granted = await api.put(`/api/v1/admin/users/${operatorId}/roles`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { roles: ['facility_operator'], reason: 'End-to-end test account' },
  });
  expect(granted.ok(), 'grant facility_operator').toBe(true);

  // Operator: draft a listing through the form, then publish it.
  const operator = await pageFor(browser, operatorEmail);
  await operator.goto('/marketplace');
  await expect(operator.getByRole('heading', { level: 1, name: 'Circular surplus marketplace' })).toBeVisible();
  await operator.getByRole('button', { name: 'New listing' }).click();
  const form = operator.getByRole('dialog', { name: 'New listing' });
  await form.getByRole('textbox', { name: 'Title' }).fill(title);
  await form.getByRole('textbox', { name: 'Quantity' }).fill('30');
  await form.getByRole('button', { name: 'Create draft' }).click();
  await expect(form).toBeHidden();
  await operator.getByRole('button', { name: `Open listing: ${title}` }).click();
  const detail = operator.getByRole('dialog', { name: title });
  await expect(detail.getByText('Draft')).toBeVisible();
  await detail.getByRole('button', { name: 'Publish' }).click();
  await expect(detail.getByText('Published', { exact: true }).first()).toBeVisible();
  await operator.keyboard.press('Escape');

  // Citizen: cannot create, finds the listing by search, asks for it.
  const citizen = await pageFor(browser, citizenEmail);
  await citizen.goto('/marketplace');
  await expect(citizen.getByRole('button', { name: 'New listing' })).toHaveCount(0);
  await citizen.getByRole('searchbox', { name: 'Search' }).fill(run);
  await citizen.getByRole('button', { name: `Open listing: ${title}` }).click();
  const ask = citizen.getByRole('dialog', { name: title });
  await ask.getByRole('textbox', { name: /Message to the owner/ }).fill('For a community hall');
  await ask.getByRole('button', { name: 'Request this' }).click();
  await expect(ask.getByText('Pending')).toBeVisible();
  await citizen.keyboard.press('Escape');

  // Operator: sees the request with contact details and accepts it.
  await operator.reload();
  await expect(operator.getByText('1 pending request')).toBeVisible();
  await operator.getByRole('button', { name: `Open listing: ${title}` }).click();
  const owner = operator.getByRole('dialog', { name: title });
  await expect(owner.getByText(citizenEmail)).toBeVisible();
  await owner.getByRole('button', { name: /^Accept request from/ }).click();
  await expect(owner.getByText('Reserved', { exact: true }).first()).toBeVisible();

  // Citizen: the decision is persisted and visible after a reload; a notification arrived.
  await citizen.reload();
  await expect(citizen.getByRole('heading', { name: 'My requests' })).toBeVisible();
  const mine = citizen.locator('li.request', { hasText: title });
  await expect(mine.getByText('Accepted')).toBeVisible();
  await citizen.goto('/notifications');
  await expect(citizen.getByText('Your request was accepted')).toBeVisible();
});
