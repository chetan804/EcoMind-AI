import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { SESSION_HINT_KEY } from './fixtures';

/**
 * Help assistant and support desk in a real browser against the real stack, no stubbing:
 *
 *   a citizen asks the assistant a question the help articles cover (the answer names its source),
 *   asks one they do not cover (the assistant says it does not know and does not guess), sends that
 *   question to the support team and chooses to share the chat -> a manager finds it in the queue,
 *   reads the shared chat, takes it, replies and marks it resolved -> the citizen sees the reply
 *   after a reload and closes the request.
 *
 * Needs E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD (roles are granted by an administrator) and the starter
 * articles (`python -m app.cli seed-support-knowledge`); without them the spec FAILS rather than skips.
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

test('ask the assistant, send an unanswered question to staff, get a reply', async ({ browser, playwright }) => {
  expect(adminEmail && adminPassword, 'E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD must be set').toBeTruthy();
  const run = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  const api = await playwright.request.newContext({ baseURL });
  const managerEmail = `manager.${run}@example.org`;
  const citizenEmail = `citizen.${run}@example.org`;
  const managerId = await signUp(api, managerEmail, `Mina Manager ${run}`);
  await signUp(api, citizenEmail, `Casey Citizen ${run}`);

  const adminLogin = await api.post('/api/v1/auth/login', { data: { email: adminEmail, password: adminPassword } });
  expect(adminLogin.ok(), 'administrator sign-in').toBe(true);
  const adminToken = ((await adminLogin.json()) as { access_token: string }).access_token;
  const granted = await api.put(`/api/v1/admin/users/${managerId}/roles`, {
    headers: { Authorization: `Bearer ${adminToken}` },
    data: { roles: ['manager'], reason: 'End-to-end test account' },
  });
  expect(granted.ok(), 'grant manager').toBe(true);

  // Citizen: a covered question is answered from an article and says where from.
  const citizen = await pageFor(browser, citizenEmail);
  await citizen.goto('/assistant');
  await expect(citizen.getByRole('heading', { level: 1, name: 'Help assistant' })).toBeVisible();
  await citizen.getByRole('button', { name: 'How do I turn on two-step sign-in?' }).click();
  const log = citizen.getByRole('log', { name: 'Conversation with the assistant' });
  await expect(log.getByText('From the help articles')).toBeVisible();
  await expect(log.getByText('How do I turn on two-step verification?')).toBeVisible(); // the source
  await expect(log.getByText(/authenticator app/)).toBeVisible();

  // An uncovered question is not guessed at.
  const question = `What is the capital of France? ${run}`;
  await citizen.getByLabel(/Your question/).fill(question);
  await citizen.getByRole('button', { name: 'Ask', exact: true }).click();
  await expect(log.getByText('No answer found')).toBeVisible();
  await expect(log.getByText(/would rather not guess/)).toBeVisible();

  // Hand the question to the support team, sharing the chat.
  await log.getByRole('button', { name: 'Send this to the support team' }).click();
  const form = citizen.getByRole('dialog', { name: 'Ask the support team' });
  await expect(form.getByRole('checkbox', { name: /read my chat/ })).not.toBeChecked();
  await form.getByRole('textbox', { name: /Subject/ }).fill(`Capital question ${run}`);
  await form.getByRole('textbox', { name: /What do you need help with/ }).fill(`${question} Please advise.`);
  await form.getByText(/read my chat/).click(); // the visible box is the label
  await expect(form.getByRole('checkbox', { name: /read my chat/ })).toBeChecked();
  await form.getByRole('button', { name: 'Send request' }).click();
  await expect(form).toBeHidden();

  // Manager: finds it in the queue, reads the shared chat, takes it, replies, resolves it.
  const manager = await pageFor(browser, managerEmail);
  await manager.goto('/support');
  await manager.getByRole('tab', { name: 'Support queue' }).click();
  await manager.getByRole('searchbox', { name: 'Search subjects' }).fill(run);
  await manager.getByRole('button', { name: `Open request: Capital question ${run}` }).click();
  const desk = manager.getByRole('dialog', { name: `Capital question ${run}` });
  await expect(desk.getByText(`From Casey Citizen ${run}`)).toBeVisible();
  await desk.getByText('Chat the requester chose to share').click();
  await expect(desk.getByText(question, { exact: true }).first()).toBeVisible();
  await desk.getByRole('button', { name: 'Assign to me' }).click();
  await expect(desk.getByText(`Handled by Mina Manager ${run}`)).toBeVisible();
  await desk.getByRole('textbox', { name: 'Reply to the requester' }).fill('That is outside what this platform covers.');
  await desk.getByRole('button', { name: 'Send reply' }).click();
  await expect(desk.getByText('That is outside what this platform covers.')).toBeVisible();
  await desk.getByLabel('Change status').selectOption('resolved');
  await expect(desk.getByText('Resolved', { exact: true }).first()).toBeVisible();

  // Citizen: the reply and the status survive a reload; closing is final.
  await citizen.goto('/support');
  await citizen.getByRole('button', { name: `Open request: Capital question ${run}` }).click();
  const mine = citizen.getByRole('dialog', { name: `Capital question ${run}` });
  await expect(mine.getByText('That is outside what this platform covers.')).toBeVisible();
  await expect(mine.getByText('Resolved', { exact: true }).first()).toBeVisible();
  await expect(mine.getByLabel('Change status')).toHaveCount(0); // staff-only control
  await mine.getByRole('button', { name: 'Close this request' }).click();
  await expect(mine.getByText(/This request is closed/)).toBeVisible();
});

test('the assistant reads only the signed-in person\'s own account', async ({ browser, playwright }) => {
  const run = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  const api = await playwright.request.newContext({ baseURL });
  const email = `points.${run}@example.org`;
  await signUp(api, email, `Pia Points ${run}`);
  const page = await pageFor(browser, email);
  await page.goto('/assistant');
  await page.getByLabel(/Your question/).fill('how many points do I have');
  await page.getByRole('button', { name: 'Ask', exact: true }).click();
  const log = page.getByRole('log', { name: 'Conversation with the assistant' });
  await expect(log.getByText('From your account')).toBeVisible();
  await expect(log.getByText(/You have 0 points/)).toBeVisible();
});
