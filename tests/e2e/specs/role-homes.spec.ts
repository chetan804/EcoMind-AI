import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext, type Browser, type Page } from '@playwright/test';
import { SESSION_HINT_KEY } from './fixtures';

/**
 * Role homes, checked in a real browser against the real backend: what each role sees on
 * /dashboard, which API calls the page makes (a role without `analytics:read` must never call the
 * analytics API), the backend's refusals for the same people when called directly, and an axe scan
 * of each home in both themes.
 *
 * Needs E2E_ADMIN_EMAIL / E2E_ADMIN_PASSWORD (to grant roles, as an administrator would).
 * Throw-away database only: it registers four accounts.
 */
const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
const PASSWORD = 'e2e test passphrase 2026';
const THEME_KEY = 'ecomind.theme';
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

interface Actor { email: string; id: string; token: string }
const bearer = (a: Actor) => ({ Authorization: `Bearer ${a.token}` });

async function signIn(api: APIRequestContext, email: string, password: string): Promise<Actor> {
  const login = await api.post('/api/v1/auth/login', { data: { email, password } });
  expect(login.ok(), `sign in ${email}`).toBe(true);
  const body = (await login.json()) as { access_token: string; user: { id: string } };
  return { email, id: body.user.id, token: body.access_token };
}

async function account(api: APIRequestContext, admin: Actor, run: string, name: string, roles: string[]): Promise<Actor> {
  const email = `home.${name}.${run}@example.org`;
  const created = await api.post('/api/v1/auth/register', { data: { email, password: PASSWORD, full_name: `Home ${name} ${run}` } });
  expect(created.ok(), `register ${email}`).toBe(true);
  const actor = await signIn(api, email, PASSWORD);
  if (roles.length) {
    const granted = await api.put(`/api/v1/admin/users/${actor.id}/roles`, { headers: bearer(admin), data: { roles, reason: 'End-to-end role home test' } });
    expect(granted.ok(), `grant ${roles.join(',')}`).toBe(true);
  }
  return signIn(api, email, PASSWORD); // a fresh token that carries the new role
}

async function open(browser: Browser, actor: Actor, theme = 'dark'): Promise<{ page: Page; analytics: string[] }> {
  const context = await browser.newContext({ baseURL, viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();
  const login = await page.request.post('/api/v1/auth/login', { data: { email: actor.email, password: PASSWORD } });
  expect(login.ok()).toBe(true);
  await page.addInitScript(([hint, key, value]) => {
    window.localStorage.setItem(hint as string, '1');
    window.localStorage.setItem(key as string, value as string);
  }, [SESSION_HINT_KEY, THEME_KEY, theme]);
  const analytics: string[] = [];
  page.on('request', (r) => { if (r.url().includes('/api/v1/analytics')) analytics.push(r.url()); });
  await page.goto('/dashboard');
  await page.locator('main').first().waitFor();
  await page.waitForLoadState('networkidle');
  return { page, analytics };
}

async function serious(page: Page, label: string): Promise<string[]> {
  const result = await new AxeBuilder({ page }).withTags(TAGS).exclude('.maplibregl-canvas-container, .gm-style').analyze();
  return result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical' || v.id === 'color-contrast')
    .map((v) => `${label} ${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
}

test('each role gets its own home and the backend refuses what the home does not offer', async ({ browser, playwright }) => {
  test.setTimeout(240_000);
  expect(adminEmail && adminPassword, 'E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD must be set').toBeTruthy();
  const run = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  const api = await playwright.request.newContext({ baseURL });
  const admin = await signIn(api, adminEmail as string, adminPassword as string);
  const citizen = await account(api, admin, run, 'citizen', []);
  const collector = await account(api, admin, run, 'collector', ['collector']);
  const operator = await account(api, admin, run, 'operator', ['facility_operator']);
  const manager = await account(api, admin, run, 'manager', ['manager']);

  // --- the pages
  const found: string[] = [];
  for (const theme of ['dark', 'light']) {
    const c = await open(browser, citizen, theme);
    await expect(c.page.getByText('What would you like to do?')).toBeVisible();
    await expect(c.page.getByRole('heading', { name: 'My open tasks' })).toHaveCount(0);
    await expect(c.page.getByText('Operations overview, last 30 days')).toHaveCount(0);
    expect(c.analytics, 'a citizen home must not call the analytics API').toEqual([]);
    found.push(...(await serious(c.page, `citizen home [${theme}]`)));
    await c.page.context().close();

    const k = await open(browser, collector, theme);
    await expect(k.page.getByRole('heading', { name: 'My open tasks' })).toBeVisible();
    await expect(k.page.getByText('Operations overview, last 30 days')).toHaveCount(0);
    expect(k.analytics, 'a collector home must not call the analytics API').toEqual([]);
    found.push(...(await serious(k.page, `collector home [${theme}]`)));
    await k.page.context().close();

    const o = await open(browser, operator, theme);
    await expect(o.page.getByText('What would you like to do?')).toBeVisible();
    await expect(o.page.getByRole('heading', { name: 'My open tasks' })).toHaveCount(0);
    expect(o.analytics, 'a facility operator home must not call the analytics API').toEqual([]);
    found.push(...(await serious(o.page, `operator home [${theme}]`)));
    await o.page.context().close();

    const m = await open(browser, manager, theme);
    await expect(m.page.getByText('Operations overview, last 30 days')).toBeVisible();
    expect(m.analytics.length, 'the manager overview reads the analytics API').toBeGreaterThan(0);
    found.push(...(await serious(m.page, `manager home [${theme}]`)));
    await m.page.context().close();
  }
  expect(found, found.join('\n')).toEqual([]);

  // --- the same people, calling the API directly
  const status = async (who: Actor, method: 'get' | 'put', path: string, data?: unknown) =>
    (await api[method](`/api/v1${path}`, { headers: bearer(who), ...(data ? { data } : {}) })).status();
  expect(await status(citizen, 'get', '/admin/users')).toBe(403);
  expect(await status(citizen, 'get', '/analytics/overview')).toBe(403);
  expect(await status(citizen, 'get', '/collection/tasks')).toBe(403);
  expect(await status(collector, 'get', '/analytics/overview')).toBe(403);
  expect(await status(collector, 'get', '/admin/users')).toBe(403);
  expect(await status(operator, 'get', '/analytics/overview')).toBe(403);
  expect(await status(operator, 'get', '/anomalies')).toBe(403);
  expect(await status(manager, 'get', '/analytics/overview')).toBe(200);
  // A manager may read the user directory (users:read) but not change anything protected.
  expect(await status(manager, 'get', '/admin/users')).toBe(200);
  expect(await status(manager, 'get', '/admin/audit-logs')).toBe(403);
  expect(await status(manager, 'get', '/admin/system')).toBe(403);
  expect(await status(manager, 'put', `/admin/users/${citizen.id}/roles`, { roles: ['manager'], reason: 'self-escalation attempt' })).toBe(403);
  expect(await status(admin, 'get', '/admin/users')).toBe(200);
  expect(await status(admin, 'get', '/admin/audit-logs')).toBe(200);
});
