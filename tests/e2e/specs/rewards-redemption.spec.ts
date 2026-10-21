import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { SESSION_HINT_KEY } from './fixtures';

/**
 * Rewards redemption in a real browser against the real stack, no stubbing:
 *
 *   an administrator adds a reward through the form (the platform ships none) and funds a citizen's
 *   points -> the citizen redeems it and is shown a claim code -> the code is still there after a
 *   reload -> the administrator finds it in the queue by code and hands it over -> the citizen sees
 *   it fulfilled, with their balance reduced by the cost.
 *
 * Needs E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD; without them the spec FAILS rather than skips.
 */
const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const PASSWORD = 'e2e test passphrase 2026'; // throw-away database only

async function signIn(browser: Browser, email: string, password: string): Promise<Page> {
  const context = await browser.newContext({ baseURL });
  const page = await context.newPage();
  const response = await page.request.post('/api/v1/auth/login', { data: { email, password } });
  expect(response.ok(), `sign in ${email}`).toBe(true);
  await page.addInitScript((key) => window.localStorage.setItem(key, '1'), SESSION_HINT_KEY);
  return page;
}

async function register(api: APIRequestContext, email: string, name: string): Promise<string> {
  const created = await api.post('/api/v1/auth/register', { data: { email, password: PASSWORD, full_name: name } });
  expect(created.ok(), `register ${email}`).toBe(true);
  const login = await api.post('/api/v1/auth/login', { data: { email, password: PASSWORD } });
  expect(login.ok(), `login ${email}`).toBe(true);
  return ((await login.json()) as { user: { id: string } }).user.id;
}

test('an administrator offers a reward, a citizen redeems it, staff hand it over', async ({ browser, playwright }) => {
  expect(adminEmail && adminPassword, 'E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD must be set').toBeTruthy();
  const run = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  const rewardName = `E2E steel bottle ${run}`;
  const citizenEmail = `rewarded.${run}@example.org`;
  const api = await playwright.request.newContext({ baseURL });
  const citizenId = await register(api, citizenEmail, `Rita Reward ${run}`);

  const adminLogin = await api.post('/api/v1/auth/login', { data: { email: adminEmail, password: adminPassword } });
  expect(adminLogin.ok(), 'administrator sign-in').toBe(true);
  const adminToken = ((await adminLogin.json()) as { access_token: string }).access_token;
  const funded = await api.post('/api/v1/rewards/adjustments', {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { user_id: citizenId, points: 300, description: 'End-to-end test funding' },
  });
  expect(funded.ok(), 'fund the citizen').toBe(true);

  // Staff: add the reward through the form.
  const admin = await signIn(browser, adminEmail ?? '', adminPassword ?? '');
  await admin.goto('/rewards');
  await admin.getByRole('tab', { name: 'Reward items' }).click();
  await admin.getByRole('button', { name: 'New reward' }).click();
  const form = admin.getByRole('dialog', { name: 'New reward' });
  await form.getByLabel('Name').fill(rewardName);
  await form.getByLabel('Description (optional)').fill('500 ml, steel');
  await form.getByLabel('Cost in points').fill('120');
  await form.getByLabel('Units in stock (leave empty for unlimited)').fill('5');
  await form.getByLabel('Limit per person (leave empty for none)').fill('1');
  await form.getByRole('button', { name: 'Add reward' }).click();
  await expect(admin.getByRole('table', { name: 'Reward items' }).getByText(rewardName)).toBeVisible();

  // Citizen: see the reward, redeem it, get a claim code.
  const citizen = await signIn(browser, citizenEmail, PASSWORD);
  await citizen.goto('/rewards');
  await expect(citizen.getByText('300', { exact: true }).first()).toBeVisible();
  await citizen.getByRole('tab', { name: 'Redeem' }).click();
  await citizen.getByRole('button', { name: `Redeem ${rewardName}` }).click();
  await citizen.getByRole('dialog', { name: `Redeem ${rewardName}` }).getByRole('button', { name: 'Redeem for 120 points' }).click();
  const claim = citizen.getByRole('dialog', { name: 'Reward redeemed' }).getByLabel('Claim code');
  await expect(claim).toBeVisible();
  const code = ((await claim.textContent()) ?? '').trim();
  expect(code).toMatch(/^[A-Z2-9]{5}-[A-Z2-9]{5}$/);
  await citizen.getByRole('button', { name: 'Done' }).click();

  // The per-person limit now applies, and the code survives a reload.
  await expect(citizen.getByRole('button', { name: `Redeem ${rewardName}` })).toBeDisabled();
  await citizen.reload();
  await citizen.getByRole('tab', { name: 'My redemptions' }).click();
  const mine = citizen.getByRole('table', { name: 'My redemptions' });
  await expect(mine.getByText(code)).toBeVisible();
  await expect(mine.getByText('Pending')).toBeVisible();

  // Staff: find it by code and hand it over.
  await admin.reload();
  await admin.getByRole('tab', { name: 'Redemption queue' }).click();
  await admin.getByLabel('Claim code').fill(code);
  const queue = admin.getByRole('table', { name: 'Redemptions' });
  await expect(queue.getByText(`Rita Reward ${run}`)).toBeVisible();
  await queue.getByRole('button', { name: `Mark ${code} handed over` }).click();
  await admin.getByRole('dialog', { name: `Hand over ${rewardName}` }).getByLabel('Note (optional)').fill('Collected at the depot');
  await admin.getByRole('button', { name: 'Mark as handed over' }).click();
  await admin.getByLabel('Status').selectOption('fulfilled');
  await expect(queue.getByText('Collected at the depot')).toBeVisible();

  // Citizen: fulfilled, nothing left to cancel, balance reduced by the cost.
  await citizen.reload();
  await citizen.getByRole('tab', { name: 'My redemptions' }).click();
  await expect(citizen.getByRole('table', { name: 'My redemptions' }).getByText('Fulfilled')).toBeVisible();
  await expect(citizen.getByRole('button', { name: /Cancel redemption of/ })).toHaveCount(0);
  await citizen.getByRole('tab', { name: 'My points' }).click();
  await expect(citizen.getByText('180', { exact: true }).first()).toBeVisible();
});
