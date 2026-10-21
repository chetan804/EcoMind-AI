import type { Page } from '@playwright/test';
import { E2E_EMAIL, E2E_PASSWORD, expect, publicTest, test } from './fixtures';

/**
 * Keyboard-only behaviour in a real browser against the real stack: no mouse, no stubbing.
 * Automated checks (axe, in accessibility.spec.ts) cannot tell whether a page can actually be
 * driven from the keyboard; these tests do. They are evidence for keyboard operability of the
 * shell and the sign-in form, NOT a substitute for a screen-reader review (not done).
 */

async function focusedSummary(page: Page) {
  return page.evaluate(() => {
    const el = document.activeElement as HTMLElement | null;
    if (!el || el === document.body) return null;
    const style = getComputedStyle(el);
    return {
      tag: el.tagName.toLowerCase(),
      label: (el.getAttribute('aria-label') ?? el.textContent ?? '').trim().slice(0, 40),
      id: el.id,
      outlineVisible: style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0,
      shadowVisible: style.boxShadow !== 'none',
    };
  });
}

publicTest.describe('sign-in with the keyboard only', () => {
  publicTest('Tab reaches the fields in order and Enter submits', async ({ page }) => {
    await page.goto('/sign-in');
    await page.locator('body').click({ position: { x: 1, y: 1 } });
    // Walk the focus order until the e-mail field, then fill and submit without touching the mouse.
    for (let i = 0; i < 15; i++) {
      await page.keyboard.press('Tab');
      if ((await page.evaluate(() => (document.activeElement as HTMLInputElement | null)?.autocomplete)) === 'email' ||
        (await page.evaluate(() => document.activeElement?.getAttribute('type'))) === 'email') break;
    }
    await expect(page.getByLabel(/Email address/)).toBeFocused();
    await page.keyboard.type(E2E_EMAIL);
    await page.keyboard.press('Tab');
    await expect(page.getByLabel(/^Password/)).toBeFocused();
    await page.keyboard.type(E2E_PASSWORD);
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});

test.describe('application shell with the keyboard only', () => {
  test('the first Tab stop is the skip link, and it moves focus to the main content', async ({ page }) => {
    await page.goto('/dashboard');
    await page.locator('main').first().waitFor();
    await page.keyboard.press('Tab');
    await expect(page.getByRole('link', { name: 'Skip to main content' })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect.poll(() => page.evaluate(() => document.activeElement?.id)).toBe('main');
  });

  test('every Tab stop shows a visible focus indicator, and focus never gets trapped', async ({ page }) => {
    await page.goto('/dashboard');
    await page.locator('main').first().waitFor();
    await page.waitForLoadState('networkidle');
    const seen = new Set<string>();
    const hidden: string[] = [];
    for (let i = 0; i < 70; i++) {
      await page.keyboard.press('Tab');
      const info = await focusedSummary(page);
      if (!info) continue;
      seen.add(`${info.tag}:${info.id}:${info.label}`);
      if (!info.outlineVisible && !info.shadowVisible) hidden.push(`${info.tag} "${info.label}"`);
    }
    expect(hidden, 'focused elements without a visible indicator').toEqual([]);
    expect(seen.size, 'distinct focusable elements reached').toBeGreaterThan(15);
    // Shift+Tab goes back (no trap): the previous stop is a different element.
    const before = await focusedSummary(page);
    await page.keyboard.press('Shift+Tab');
    expect(await focusedSummary(page)).not.toEqual(before);
  });

  test('the account menu opens and closes from the keyboard and returns focus', async ({ page }) => {
    await page.goto('/dashboard');
    const trigger = page.getByRole('button', { name: 'Account menu' });
    await trigger.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('menuitem', { name: 'Sign out' })).toBeVisible();
    await page.keyboard.press('ArrowDown');
    expect((await focusedSummary(page))?.tag).not.toBe('body');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('menuitem', { name: 'Sign out' })).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test('the page search dialog takes focus, closes with Escape and gives focus back', async ({ page }) => {
    await page.goto('/dashboard');
    const trigger = page.getByRole('button', { name: 'Search pages' });
    await trigger.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('dialog', { name: 'Search pages' })).toBeVisible();
    await expect(page.getByLabel('Page name')).toBeFocused();
    await page.keyboard.type('class');
    await expect(page.getByRole('dialog').getByRole('link', { name: /classification/i }).first()).toBeVisible();
    // In a search box the browser uses the first Escape to clear the text; the next one closes.
    await page.keyboard.press('Escape');
    await expect(page.getByLabel('Page name')).toHaveValue('');
    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test('the navigation drawer works from the keyboard on a phone-sized screen', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 800 });
    await page.goto('/dashboard');
    const open = page.getByRole('button', { name: 'Open navigation' });
    await open.focus();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('button', { name: 'Close navigation' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(open).toBeFocused();
    // While the drawer is closed its links are not reachable by Tab.
    await page.keyboard.press('Tab');
    const next = await focusedSummary(page);
    expect(next?.label ?? '').not.toMatch(/Classification|Marketplace|Incidents/);
  });

  test('a keyboard user can navigate to another page and sign out from the sidebar', async ({ page }) => {
    await page.goto('/dashboard');
    const link = page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Classification' });
    await link.focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/classify$/);
    const signOut = page.getByRole('button', { name: 'Sign out' });
    await signOut.focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/sign-in$/);
  });
});
