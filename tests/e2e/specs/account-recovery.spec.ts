import { randomBytes } from 'node:crypto';
import { expect, publicTest } from './fixtures';
import { latestMailLink, mailAvailable, mailSource, messagesTo, waitForMailLink, waitForMessage } from './mail';

// Real browser, real backend, real database. The e-mails are read from a Mailpit inbox that the
// backend delivers to over SMTP (CI), or from the backend's console log (development); see mail.ts.
// No network stubbing.

publicTest.skip(!mailAvailable, 'Neither E2E_MAILPIT_URL nor E2E_MAIL_LOG_COMMAND is set: cannot read the e-mailed links');
const viaMailpit = mailSource === 'mailpit';

const PASSWORD = 'first passphrase for e2e 2026';
const NEW_PASSWORD = 'second passphrase for e2e 2026';

// A unique address per run, so repeated runs against one database never collide.
const newAddress = () => `recovery.${randomBytes(4).toString('hex')}@example.org`;

async function signUp(page: import('@playwright/test').Page, email: string): Promise<void> {
  await page.goto('/sign-up');
  await page.getByLabel(/Full name/).fill('Recovery Tester');
  await page.getByLabel(/Email address/).fill(email);
  await page.getByLabel(/^Password/).fill(PASSWORD);
  await page.getByLabel(/Confirm password/).fill(PASSWORD);
  await page.getByRole('button', { name: 'Create account' }).click();
  await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
}

publicTest.describe('account recovery journey', () => {
  publicTest('a password can be reset with a one-time link, which works once and leaves no token in the address bar', async ({ page }) => {
    const email = newAddress();
    await signUp(page, email);
    await page.getByRole('button', { name: 'Account menu' }).click();
    await page.getByRole('menuitem', { name: 'Sign out' }).click();

    await page.goto('/sign-in');
    await page.getByRole('link', { name: 'Forgot password?' }).click();
    await expect(page).toHaveURL(/\/forgot-password$/);
    await page.getByLabel(/Email address/).fill(email);
    await page.getByRole('button', { name: 'Send reset link' }).click();
    await expect(page.getByRole('heading', { name: 'Check your inbox' })).toBeVisible();

    const link = await waitForMailLink(email, 'reset-password');
    expect(link).toContain('#token=');
    if (viaMailpit) {
      // What arrived is a real SMTP delivery, not a log line.
      const mail = await waitForMessage(email, (m) => m.subject === 'Reset your EcoMind AI password');
      expect(mail.from).toBe('no-reply@example.org');
      expect(mail.to).toEqual([email]);
      expect(mail.username, 'the backend authenticated to the SMTP server').not.toBe('');
      expect(mail.text).toContain('Recovery Tester');
      expect(new URL(link).search, 'the token travels in the fragment, never the query string').toBe('');
    }
    await page.goto(link);
    await page.getByLabel(/^New password/).fill(NEW_PASSWORD);
    await page.getByLabel(/Confirm new password/).fill(NEW_PASSWORD);
    // The token is scrubbed from the address bar (and so from history and screenshots).
    await expect.poll(() => new URL(page.url()).hash).toBe('');
    await page.getByRole('button', { name: 'Change password' }).click();
    await expect(page.getByRole('heading', { name: 'Password changed' })).toBeVisible();

    // The old password is gone, the new one works.
    await page.getByRole('link', { name: 'Go to sign in' }).click();
    await page.getByLabel(/Email address/).fill(email);
    await page.getByLabel(/^Password/).fill(PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('alert')).toContainText('Incorrect email or password.');
    await page.getByLabel(/^Password/).fill(NEW_PASSWORD);
    await page.getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByRole('button', { name: 'Account menu' })).toBeVisible();
    if (viaMailpit) {
      // A password change is announced by e-mail, and that notice carries no link to steal.
      const notice = await waitForMessage(email, (m) => m.subject === 'Your EcoMind AI password was changed');
      expect(notice.text).not.toMatch(/#token=/);
    }

    // The same link cannot be used again.
    await page.goto(link);
    await page.getByLabel(/^New password/).fill('third passphrase for e2e 2026');
    await page.getByLabel(/Confirm new password/).fill('third passphrase for e2e 2026');
    await page.getByRole('button', { name: 'Change password' }).click();
    await expect(page.getByText('This link no longer works')).toBeVisible();
  });

  publicTest('asking for a reset for an unknown address looks exactly the same and sends nothing', async ({ page }) => {
    const unknown = newAddress();
    await page.goto('/forgot-password');
    await page.getByLabel(/Email address/).fill(unknown);
    await page.getByRole('button', { name: 'Send reset link' }).click();
    await expect(page.getByRole('heading', { name: 'Check your inbox' })).toBeVisible();
    await expect(page.getByText('If an account exists for that address')).toBeVisible();
    await page.waitForTimeout(2000); // the mail (if any) is sent after the response
    expect(await latestMailLink(unknown, 'reset-password')).toBeNull();
    if (viaMailpit) expect(await messagesTo(unknown), 'nothing at all is sent to an unknown address').toEqual([]);
  });

  publicTest('a new account is asked to confirm its address, and the e-mailed link confirms it', async ({ page }) => {
    const email = newAddress();
    await signUp(page, email);
    await expect(page.getByText('Confirm your email address')).toBeVisible();

    const link = await waitForMailLink(email, 'verify-email');
    if (viaMailpit) {
      const mail = await waitForMessage(email, (m) => m.subject === 'Confirm your EcoMind AI e-mail address');
      expect(mail.from).toBe('no-reply@example.org');
      expect(mail.username).not.toBe('');
    }
    await page.goto(link);
    // Opening the link alone confirms nothing: a button press is required.
    await expect(page.getByRole('heading', { name: 'Confirm your email' })).toBeVisible();
    await page.getByRole('button', { name: 'Confirm my email address' }).click();
    await expect(page.getByRole('heading', { name: 'Email confirmed' })).toBeVisible();

    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
    await expect(page.getByText('Confirm your email address')).toHaveCount(0);
  });

  publicTest('an incomplete link says so instead of failing silently', async ({ page }) => {
    await page.goto('/reset-password');
    await expect(page.getByText('This link is incomplete')).toBeVisible();
    await page.goto('/verify-email#token=short');
    await expect(page.getByText('This link is incomplete')).toBeVisible();
  });
});
