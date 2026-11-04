import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

/**
 * Automated WCAG 2.2 A/AA scan (axe-core) of the PUBLIC pages (landing, the walkthrough dialog and
 * every authentication screen) in both themes and at desktop and phone width. It complements
 * accessibility.spec.ts, which covers the signed-in pages. As there, this is evidence of no
 * *detectable* serious violation, not of full conformance: keyboard order and screen-reader
 * wording still need the manual review in docs/testing/ACCESSIBILITY_MANUAL_CHECKLIST.md.
 */
const THEME_KEY = 'ecomind.theme';
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const ROUTES = ['/', '/sign-in', '/sign-up', '/forgot-password', '/reset-password', '/verify-email'];
const SIZES = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'phone', width: 390, height: 844 },
] as const;

async function violations(page: Page, label: string): Promise<string[]> {
  await page.locator('main, [role="dialog"]').first().waitFor();
  await page.waitForLoadState('networkidle');
  const result = await new AxeBuilder({ page })
    .withTags(TAGS)
    .exclude('.maplibregl-canvas-container, .gm-style')
    .analyze();
  return result.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical' || v.id === 'color-contrast')
    .map((v) => `${label} ${v.id} (${v.impact}): ${v.nodes.slice(0, 3).map((n) => n.target.join(' ')).join(' | ')}`);
}

for (const theme of ['dark', 'light'] as const) {
  for (const size of SIZES) {
    test(`no serious accessibility violations on the public pages (${theme} theme, ${size.name})`, async ({ browser }) => {
      test.setTimeout(180_000);
      const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
      const context = await browser.newContext({ baseURL, viewport: { width: size.width, height: size.height } });
      const page = await context.newPage();
      await page.addInitScript(([key, value]) => window.localStorage.setItem(key as string, value as string), [THEME_KEY, theme]);
      const found: string[] = [];
      for (const route of ROUTES) {
        await page.goto(route);
        found.push(...(await violations(page, `${route} [${theme}/${size.name}]`)));
      }
      // The walkthrough is a modal dialog: scan it open, too.
      await page.goto('/');
      await page.getByRole('button', { name: 'Watch demo' }).first().click();
      await expect(page.getByRole('dialog', { name: 'Product walkthrough' })).toBeVisible();
      found.push(...(await violations(page, `walkthrough dialog [${theme}/${size.name}]`)));
      await context.close();
      expect(found, found.join('\n')).toEqual([]);
    });
  }
}
