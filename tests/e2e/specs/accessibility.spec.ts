import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { SESSION_HINT_KEY } from './fixtures';

/**
 * Automated WCAG 2.2 A/AA scan (axe-core) of every signed-in page in both themes, as an
 * administrator so that no navigation entry is hidden. Automated rules find roughly a third of
 * accessibility problems: this is evidence of no *detectable* violations, not of full conformance
 * (keyboard order, screen-reader wording and the like need manual review; see docs/security and
 * docs/project-completion/LIMITATIONS.md).
 *
 * Needs E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD; without them the spec FAILS rather than skips.
 */
const adminEmail = process.env.E2E_ADMIN_EMAIL;
const adminPassword = process.env.E2E_ADMIN_PASSWORD;
const THEME_KEY = 'ecomind.theme';
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const ROUTES = [
  '/dashboard', '/classify', '/classify/review', '/forecasts', '/anomalies', '/routes', '/marketplace', '/incidents',
  '/sorting-guide', '/passports', '/recovery', '/rewards', '/reports', '/locations', '/facilities', '/fleet',
  '/collection', '/analytics', '/notifications', '/settings/system-status',
];

async function violations(page: Page, route: string): Promise<string[]> {
  await page.goto(route);
  await page.locator('main').first().waitFor();
  await page.waitForLoadState('networkidle');
  const result = await new AxeBuilder({ page })
    .withTags(TAGS)
    .exclude('.maplibregl-canvas-container, .gm-style') // third-party map internals
    .analyze();
  return result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical' || v.id === 'color-contrast')
    .map((v) => `${route} ${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
}

for (const theme of ['dark', 'light'] as const) {
  test(`no serious accessibility violations on any signed-in page (${theme} theme)`, async ({ browser }) => {
    test.setTimeout(240_000);
    expect(adminEmail && adminPassword, 'E2E_ADMIN_EMAIL and E2E_ADMIN_PASSWORD must be set').toBeTruthy();
    const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
    const context = await browser.newContext({ baseURL, viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    const login = await page.request.post('/api/v1/auth/login', { data: { email: adminEmail, password: adminPassword } });
    expect(login.ok(), 'administrator sign-in').toBe(true);
    await page.addInitScript(([hint, key, value]) => {
      window.localStorage.setItem(hint as string, '1');
      window.localStorage.setItem(key as string, value as string);
    }, [SESSION_HINT_KEY, THEME_KEY, theme]);
    const found: string[] = [];
    for (const route of ROUTES) found.push(...(await violations(page, route)));
    expect(found, found.join('\n')).toEqual([]);
  });
}
