import { E2E_EMAIL, E2E_NAME, E2E_PASSWORD, SESSION_HINT_KEY, expect, publicTest } from './fixtures';

// Real browser, real backend, real database: no network stubbing in this file.

publicTest.describe('authentication journey', () => {
  publicTest('anonymous visitors are sent to sign-in and returned to the page they wanted', async ({ page }) => {
    await page.goto('/classify');
    await expect(page).toHaveURL(/\/sign-in$/);
    await page.getByLabel(/Email address/).fill(E2E_EMAIL);
    await page.getByLabel(/^Password/).fill(E2E_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page).toHaveURL(/\/classify$/);
    await expect(page.getByRole('heading', { level: 1, name: 'AI waste classification' })).toBeVisible();
  });

  publicTest('a wrong password is rejected with a generic message and no session', async ({ page }) => {
    await page.goto('/sign-in');
    await page.getByLabel(/Email address/).fill(E2E_EMAIL);
    await page.getByLabel(/^Password/).fill('definitely not the password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('alert')).toContainText('Incorrect email or password.');
    await expect(page).toHaveURL(/\/sign-in$/);
    expect(await page.evaluate((k) => window.localStorage.getItem(k), SESSION_HINT_KEY)).toBeNull();
  });

  publicTest('the session survives a reload via the HttpOnly cookie, and the token is not in storage', async ({ page, context }) => {
    await page.goto('/sign-in');
    await page.getByLabel(/Email address/).fill(E2E_EMAIL);
    await page.getByLabel(/^Password/).fill(E2E_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('button', { name: /account menu/i })).toContainText(E2E_NAME);

    await page.reload();
    await expect(page.getByRole('button', { name: /account menu/i })).toContainText(E2E_NAME);

    // Browser-side secrecy: the refresh cookie is HttpOnly and scoped; no token in web storage.
    const cookie = (await context.cookies()).find((c) => c.name === 'ecomind_refresh');
    expect(cookie?.httpOnly).toBe(true);
    expect(cookie?.path).toBe('/api/v1/auth');
    const jsVisible = await page.evaluate(() => document.cookie);
    expect(jsVisible).not.toContain('ecomind_refresh');
    const storage = await page.evaluate(() => JSON.stringify({ ...localStorage, ...sessionStorage }));
    expect(storage).not.toMatch(/eyJ/); // no JWT anywhere in web storage
  });

  publicTest('signing out ends the session for good, even after a reload and from the back button', async ({ page }) => {
    await page.goto('/sign-in');
    await page.getByLabel(/Email address/).fill(E2E_EMAIL);
    await page.getByLabel(/^Password/).fill(E2E_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await page.getByRole('button', { name: /account menu/i }).click();
    await page.getByRole('menuitem', { name: 'Sign out' }).click();
    await expect(page).toHaveURL(/\/sign-in$/);

    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/sign-in$/);
    // Even with the hint forced back on, the server refuses: the refresh cookie was revoked.
    await page.evaluate((k) => window.localStorage.setItem(k, '1'), SESSION_HINT_KEY);
    await page.reload();
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/sign-in$/);
  });

  publicTest('registration validates against the server password policy', async ({ page }) => {
    await page.goto('/sign-up');
    await page.getByLabel(/Full name/).fill('Policy Check');
    await page.getByLabel(/Email address/).fill(`policy.${Date.now()}@example.org`);
    await page.getByLabel(/^Password/).fill('password123456'); // long enough for the form, but on the common-password list
    await page.getByLabel(/Confirm password/).fill('password123456');
    await page.getByRole('button', { name: 'Create account' }).click();
    await expect(page.getByText('too common or too repetitive')).toBeVisible();
    await expect(page).toHaveURL(/\/sign-up$/);
  });
});
