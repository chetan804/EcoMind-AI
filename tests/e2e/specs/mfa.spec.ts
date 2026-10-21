import { randomBytes } from 'node:crypto';
import type { Page } from '@playwright/test';
import { expect, publicTest } from './fixtures';
import { totp } from './totp';

// Real browser, real backend, real database. The authenticator is simulated by computing the
// RFC 6238 code from the secret the page shows (no phone is involved, and nothing is stubbed).

const PASSWORD = 'mfa passphrase for e2e 2026';
const STEP_MS = 30_000;

publicTest.describe('two-step verification', () => {
  publicTest('the algorithm matches the RFC 6238 test vector', () => {
    // RFC 6238 appendix B, SHA-1: secret "12345678901234567890", T = 59 s -> 94287082 (8 digits).
    const secret = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ';
    expect(totp(secret, 59_000, 8)).toBe('94287082');
    expect(totp(secret, 59_000, 6)).toBe('287082');
  });
});

const newAddress = () => `mfa.${randomBytes(4).toString('hex')}@example.org`;

async function signUp(page: Page, email: string): Promise<void> {
  await page.goto('/sign-up');
  await page.getByLabel(/Full name/).fill('MFA Tester');
  await page.getByLabel(/Email address/).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByLabel(/Confirm password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
}

async function signOut(page: Page): Promise<void> {
  // The sidebar's own button: it exists on every page, including the security page itself.
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
}

async function startSignIn(page: Page, email: string): Promise<void> {
  await page.goto('/sign-in');
  await page.getByLabel(/Email address/).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Two-step verification' })).toBeVisible();
}

/** Walks the real enrolment screen; returns the secret and the recovery codes shown once. */
async function enrol(page: Page): Promise<{ secret: string; codes: string[]; usedAtMs: number }> {
  await page.goto('/settings/security');
  await page.getByRole('button', { name: 'Set up two-step verification' }).click();
  const secret = ((await page.locator('.secret').textContent()) ?? '').replace(/\s/g, '');
  expect(secret).toMatch(/^[A-Z2-7]{16,}$/);
  const usedAtMs = Date.now();
  await page.getByLabel('Code from your app').fill(totp(secret, usedAtMs));
  await page.getByRole('button', { name: 'Confirm and turn on' }).click();
  await expect(page.getByText('Save these recovery codes now')).toBeVisible();
  const codes = (await page.getByRole('list', { name: 'Recovery codes' }).getByRole('listitem').allTextContents()).map((c) => c.trim());
  expect(codes.length).toBeGreaterThanOrEqual(8);
  await page.getByLabel(/I have saved these codes/).check();
  await page.getByRole('button', { name: 'Done' }).click();
  return { secret, codes, usedAtMs };
}

publicTest.describe('two-step verification in the browser', () => {
  publicTest('enrol with a computed code, then sign in with it; a code cannot be replayed; wrong codes fail', async ({ page }) => {
    const email = newAddress();
    await signUp(page, email);
    const { secret, usedAtMs } = await enrol(page);
    await expect(page.getByText(/recovery codes left/)).toBeVisible();
    await signOut(page);

    // A wrong code is refused and nothing is signed in.
    await startSignIn(page, email);
    await page.getByLabel('Verification code').fill('000000');
    await page.getByRole('button', { name: 'Verify and sign in' }).click();
    await expect(page.getByRole('alert')).toContainText('Could not verify');
    await expect(page.getByRole('button', { name: 'Sign out' })).toHaveCount(0);

    // The code of the NEXT 30 s step is valid (one step of clock drift is tolerated) and newer than
    // the one used to enrol, so it is accepted exactly once.
    const next = totp(secret, usedAtMs + STEP_MS);
    await page.getByLabel('Verification code').fill(next);
    await page.getByRole('button', { name: 'Verify and sign in' }).click();
    await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
    await signOut(page);

    // Replaying that same code is refused.
    await startSignIn(page, email);
    await page.getByLabel('Verification code').fill(next);
    await page.getByRole('button', { name: 'Verify and sign in' }).click();
    await expect(page.getByRole('alert')).toContainText('Could not verify');
    await expect(page.getByRole('button', { name: 'Sign out' })).toHaveCount(0);
  });

  publicTest('a recovery code signs in once and never again', async ({ page }) => {
    const email = newAddress();
    await signUp(page, email);
    const { codes } = await enrol(page);
    const [first] = codes;
    expect(first).toBeTruthy();
    await signOut(page);

    await startSignIn(page, email);
    await page.getByLabel('Verification code').fill(first ?? '');
    await page.getByRole('button', { name: 'Verify and sign in' }).click();
    await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
    await signOut(page);

    await startSignIn(page, email);
    await page.getByLabel('Verification code').fill(first ?? '');
    await page.getByRole('button', { name: 'Verify and sign in' }).click();
    await expect(page.getByRole('alert')).toContainText('Could not verify');
  });
});

// Forced enrolment needs a backend that REQUIRES two-step verification for the account's role (the
// default stack does not: it would make every other spec enrol first). Point these at a second
// stack, for example a backend started with ENVIRONMENT=production (administrators and managers
// are required by default) or MFA_REQUIRED_ROLES=citizen, and a FRESH account that holds such a role
// (enrolment is permanent, so each run needs a new one):
//   E2E_ENFORCED_URL=http://localhost:5174 E2E_ENFORCED_EMAIL=... E2E_ENFORCED_PASSWORD=...
const enforcedUrl = process.env.E2E_ENFORCED_URL;
const enforcedEmail = process.env.E2E_ENFORCED_EMAIL;
const enforcedPassword = process.env.E2E_ENFORCED_PASSWORD;

publicTest.describe('forced enrolment for a role that requires two-step verification', () => {
  publicTest.skip(!enforcedUrl || !enforcedEmail || !enforcedPassword, 'E2E_ENFORCED_URL/EMAIL/PASSWORD are not set (needs a stack that enforces MFA)');
  publicTest.use({ baseURL: enforcedUrl });

  publicTest('the account can reach nothing but the security page until it has enrolled', async ({ page }) => {
    await page.goto('/sign-in');
    await page.getByLabel(/Email address/).fill(enforcedEmail ?? '');
    await page.getByLabel(/^Password/).fill(enforcedPassword ?? '');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('heading', { name: 'Security', level: 1 })).toBeVisible();
    await expect(page.getByText('Set up two-step verification to continue')).toBeVisible();

    // Every other page sends the person back here.
    for (const path of ['/dashboard', '/analytics', '/settings/users']) {
      await page.goto(path);
      await expect(page.getByText('Set up two-step verification to continue')).toBeVisible();
    }
    // The API refuses the data too (not just the UI hiding it).
    const login = await page.request.post('/api/v1/auth/login', {
      data: { email: enforcedEmail, password: enforcedPassword },
    });
    expect(login.ok()).toBe(true);
    const { access_token: token } = (await login.json()) as { access_token: string };
    const blocked = await page.request.get('/api/v1/admin/users', { headers: { Authorization: `Bearer ${token}` } });
    expect(blocked.status()).toBe(403);
    expect(((await blocked.json()) as { error: { code: string } }).error.code).toBe('mfa_enrollment_required');

    const { secret } = await enrol(page);
    expect(secret.length).toBeGreaterThan(15);
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole('heading', { name: 'Weekly collected weight' })).toBeVisible();
    await expect(page.getByText('Set up two-step verification to continue')).toHaveCount(0);
  });
});
