import { test as base, expect, type APIRequestContext } from '@playwright/test';

/**
 * Fixtures for specs that run against the real stack (frontend + backend + PostgreSQL).
 *
 * `test` gives each test a `page` that is already signed in as a real account, created through
 * the real API (no stubbing). `publicTest` is the plain Playwright test for public pages.
 *
 * The account is ensured, not created per test: the backend limits registrations per IP, and only
 * successful registrations count, so repeat runs and parallel workers are safe.
 */
export const E2E_EMAIL = 'e2e.user@example.org';
// Test-only credential for a throw-away e2e database; not used anywhere else.
export const E2E_PASSWORD = 'e2e test passphrase 2026';
export const E2E_NAME = 'E2E Tester';
export const SESSION_HINT_KEY = 'ecomind.session-hint';

const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';

export async function ensureAccount(api: APIRequestContext): Promise<void> {
  // Register first, then sign in. Signing in first would record a *failed* login on a fresh
  // database, and a few parallel workers doing that would trip the brute-force lockout.
  // 409 (already registered) is expected on every run after the first and is not a failure event.
  const created = await api.post('/api/v1/auth/register', {
    data: { email: E2E_EMAIL, password: E2E_PASSWORD, full_name: E2E_NAME },
  });
  if (!created.ok() && created.status() !== 409) {
    throw new Error(`Could not create the e2e account: ${created.status()} ${await created.text()}`);
  }
  const login = await api.post('/api/v1/auth/login', { data: { email: E2E_EMAIL, password: E2E_PASSWORD } });
  if (!login.ok()) throw new Error(`The e2e account cannot sign in: ${login.status()} ${await login.text()}`);
}

// Both variants make sure the account exists first (auto, once per worker), so a spec that
// signs in through the form never races the account's creation.
const withAccount = base.extend<object, { account: void }>({
  account: [
    async ({ playwright }, use) => {
      const api = await playwright.request.newContext({ baseURL });
      await ensureAccount(api);
      await api.dispose();
      await use();
    },
    { scope: 'worker', auto: true },
  ],
});

/** Plain browser page, signed out. The e2e account exists. */
export const publicTest = withAccount;

/** Browser page already signed in as the e2e account. */
export const test = withAccount.extend({
  page: async ({ page }, use) => {
    // Real sign-in: the HttpOnly refresh cookie lands in this browser context, exactly as after
    // using the form. The hint tells the app to restore the session from it on load.
    const response = await page.request.post('/api/v1/auth/login', {
      data: { email: E2E_EMAIL, password: E2E_PASSWORD },
    });
    expect(response.ok(), 'e2e sign-in').toBe(true);
    await page.addInitScript((key) => window.localStorage.setItem(key, '1'), SESSION_HINT_KEY);
    await use(page);
  },
});

export { expect };
