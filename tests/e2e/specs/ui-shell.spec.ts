import { expect, test } from '@playwright/test';

// These specs need only the frontend (no API, no database): the screens under test render
// demonstration or "not available yet" content and never call the backend.

test('landing page leads to sign-up and sign-in', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1, name: /Waste Management/ })).toBeVisible();
  await page.getByRole('link', { name: 'Get started' }).click();
  await expect(page).toHaveURL(/\/sign-up$/);
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();
  await page.getByRole('link', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
});

test('sign-in validates, and a valid submission is honestly reported as unavailable', async ({ page }) => {
  const apiCalls: string[] = [];
  page.on('request', (request) => {
    // fetch/XHR only: the dev server also serves source modules whose paths contain "/api/".
    if (['fetch', 'xhr'].includes(request.resourceType())) apiCalls.push(request.url());
  });
  await page.goto('/sign-in');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('Enter your email address.')).toBeVisible();
  await page.getByLabel(/Email address/).fill('someone@example.org');
  await page.getByLabel(/^Password/).fill('anything');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByText('Sign-in is not available yet')).toBeVisible();
  expect(apiCalls).toEqual([]);
});

test('page search is a real modal: focus moves in, Escape closes it and focus returns', async ({ page }) => {
  await page.goto('/dashboard');
  const trigger = page.getByRole('button', { name: 'Search pages…' });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: 'Search pages' });
  await expect(dialog).toBeVisible();
  await expect(page.getByRole('searchbox', { name: 'Page name' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
});

test('the primary navigation never offers Smart Bins & Telemetry', async ({ page }) => {
  await page.goto('/dashboard');
  const nav = page.getByRole('navigation', { name: 'Main' });
  await expect(nav.getByRole('link', { name: /^Dashboard/ })).toHaveAttribute('aria-current', 'page');
  await expect(nav.getByText(/bins|telemetry/i)).toHaveCount(0);
});

test.describe('on a phone', () => {
  test.use({ viewport: { width: 390, height: 844 } });

  for (const path of ['/', '/sign-in', '/sign-up', '/dashboard', '/classify']) {
    test(`${path} does not scroll horizontally`, async ({ page }) => {
      await page.goto(path);
      await page.waitForLoadState('networkidle');
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBe(0);
    });
  }

  test('the navigation drawer opens and traps Escape', async ({ page }) => {
    await page.goto('/dashboard');
    const open = page.getByRole('button', { name: 'Open navigation' });
    await open.click();
    await expect(open).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByRole('navigation', { name: 'Main' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(open).toHaveAttribute('aria-expanded', 'false');
    await expect(open).toBeFocused();
  });
});
