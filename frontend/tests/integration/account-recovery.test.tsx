import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RouterProvider } from 'react-router/dom';
import { createTestRouter } from '@/app/router';
import { errorReply, routeApi } from '../helpers/api-mock';
import { dataCalls, resetSession, testUser } from '../helpers/session';

const fetchSpy = vi.fn();
const TOKEN = 'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG';
const CONFIG = { password_reset_available: true, email_verification_available: true, email_verification_required: false };
const ACCEPTED = { detail: 'If an account exists for this address, a message is on its way.' };

beforeEach(() => {
  resetSession();
  fetchSpy.mockReset();
  vi.stubGlobal('fetch', fetchSpy);
});
afterEach(() => vi.unstubAllGlobals());

function renderAt(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <RouterProvider router={createTestRouter([path])} />
    </QueryClientProvider>,
  );
}

/** Anonymous visitor: only the listed routes answer. */
function anonymousApi(routes: Record<string, unknown>) {
  const calls: Array<{ key: string; body: unknown }> = [];
  fetchSpy.mockImplementation((url: string, init?: RequestInit) => {
    const key = `${(init?.method ?? 'GET').toUpperCase()} ${new URL(String(url), 'http://localhost').pathname}`;
    calls.push({ key, body: typeof init?.body === 'string' ? JSON.parse(init.body) : null });
    const reply = routes[key];
    if (reply === undefined) return Promise.resolve(errorReply(404, 'not_found', `No test route for ${key}`));
    return Promise.resolve(reply instanceof Response ? reply : Response.json(reply));
  });
  return calls;
}

describe('forgot password', () => {
  it('sends the address and shows the same confirmation whatever the account situation is', async () => {
    const calls = anonymousApi({
      'GET /api/v1/auth/config': CONFIG,
      'POST /api/v1/auth/password-reset/request': new Response(JSON.stringify(ACCEPTED), { status: 202 }),
    });
    renderAt('/forgot-password');
    await userEvent.type(await screen.findByLabelText(/Email address/), 'nobody@example.org');
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }));
    expect(await screen.findByRole('heading', { name: 'Check your inbox' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('If an account exists for that address');
    expect(calls.find((c) => c.key.endsWith('/password-reset/request'))?.body).toEqual({ email: 'nobody@example.org' });
  });

  it('validates the address before calling the server', async () => {
    anonymousApi({ 'GET /api/v1/auth/config': CONFIG });
    renderAt('/forgot-password');
    await userEvent.type(await screen.findByLabelText(/Email address/), 'not-an-address');
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }));
    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalledTimes(1); // only the config request
  });

  it('says honestly that it is unavailable when the server cannot send e-mail', async () => {
    anonymousApi({ 'GET /api/v1/auth/config': { ...CONFIG, password_reset_available: false } });
    renderAt('/forgot-password');
    expect(await screen.findByText('Password reset by e-mail is not enabled')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send reset link' })).not.toBeInTheDocument();
  });

  it('reports a server failure and a throttle without pretending the e-mail was sent', async () => {
    anonymousApi({
      'GET /api/v1/auth/config': CONFIG,
      'POST /api/v1/auth/password-reset/request': new Response(JSON.stringify({ error: { code: 'rate_limited', message: 'slow down' } }), {
        status: 429,
        headers: { 'Retry-After': '120' },
      }),
    });
    renderAt('/forgot-password');
    await userEvent.type(await screen.findByLabelText(/Email address/), 'asha@example.org');
    await userEvent.click(screen.getByRole('button', { name: 'Send reset link' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many attempts. Try again in 2 minutes.');
    expect(screen.queryByRole('heading', { name: 'Check your inbox' })).not.toBeInTheDocument();
  });
});

describe('reset password', () => {
  it('reads the token from the fragment, removes it from the address bar and submits the new password', async () => {
    const calls = anonymousApi({ 'POST /api/v1/auth/password-reset/confirm': new Response(null, { status: 204 }) });
    renderAt(`/reset-password#token=${TOKEN}`);
    await userEvent.type(await screen.findByLabelText(/^New password/), 'a brand new passphrase');
    await userEvent.type(screen.getByLabelText(/Confirm new password/), 'a brand new passphrase');
    await waitFor(() => expect(window.location.hash).toBe(''));
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(await screen.findByRole('heading', { name: 'Password changed' })).toBeInTheDocument();
    expect(calls[0]).toEqual({ key: 'POST /api/v1/auth/password-reset/confirm', body: { token: TOKEN, new_password: 'a brand new passphrase' } });
    expect(screen.getByRole('link', { name: 'Go to sign in' })).toHaveAttribute('href', '/sign-in');
  });

  it('checks the confirmation locally', async () => {
    anonymousApi({});
    renderAt(`/reset-password#token=${TOKEN}`);
    await userEvent.type(await screen.findByLabelText(/^New password/), 'a brand new passphrase');
    await userEvent.type(screen.getByLabelText(/Confirm new password/), 'something else entirely');
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(await screen.findByText('The passwords do not match.')).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('shows the server password-policy message on the field and lets the person retry', async () => {
    anonymousApi({
      'POST /api/v1/auth/password-reset/confirm': Response.json(
        { error: { code: 'weak_password', message: 'weak', details: [{ message: 'This password is too common or too repetitive.' }] } },
        { status: 422 },
      ),
    });
    renderAt(`/reset-password#token=${TOKEN}`);
    await userEvent.type(await screen.findByLabelText(/^New password/), 'passwordpassword');
    await userEvent.type(screen.getByLabelText(/Confirm new password/), 'passwordpassword');
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(await screen.findByText('This password is too common or too repetitive.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Change password' })).toBeInTheDocument();
  });

  it('offers a new link when the link is expired or used', async () => {
    anonymousApi({ 'POST /api/v1/auth/password-reset/confirm': errorReply(400, 'invalid_or_expired_token', 'expired') });
    renderAt(`/reset-password#token=${TOKEN}`);
    await userEvent.type(await screen.findByLabelText(/^New password/), 'a brand new passphrase');
    await userEvent.type(screen.getByLabelText(/Confirm new password/), 'a brand new passphrase');
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }));
    expect(await screen.findByText('This link no longer works')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Request a new link' })).toHaveAttribute('href', '/forgot-password');
    expect(screen.queryByRole('button', { name: 'Change password' })).not.toBeInTheDocument();
  });

  it.each(['', '#token=short', '#token=has spaces and ??? in it xxxxxxxxxxxxxxxxxxxx', '#other=1'])('treats %j as an incomplete link', async (hash) => {
    anonymousApi({});
    renderAt(`/reset-password${hash}`);
    expect(await screen.findByText('This link is incomplete')).toBeInTheDocument();
    expect(screen.queryByLabelText(/^New password/)).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});

describe('verify e-mail', () => {
  it('needs a click to use the link and then confirms', async () => {
    const calls = anonymousApi({ 'POST /api/v1/auth/email-verification/confirm': new Response(null, { status: 204 }) });
    renderAt(`/verify-email#token=${TOKEN}`);
    const button = await screen.findByRole('button', { name: 'Confirm my email address' });
    expect(calls).toHaveLength(0); // opening the page alone does not consume the link
    await userEvent.click(button);
    expect(await screen.findByRole('heading', { name: 'Email confirmed' })).toBeInTheDocument();
    expect(calls[0]?.body).toEqual({ token: TOKEN });
  });

  it('reports a link that no longer works', async () => {
    anonymousApi({ 'POST /api/v1/auth/email-verification/confirm': errorReply(400, 'invalid_or_expired_token', 'expired') });
    renderAt(`/verify-email#token=${TOKEN}`);
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm my email address' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('This link is invalid or has expired.');
  });
});

describe('verification banner and sign-in', () => {
  it('asks an unverified, signed-in user to confirm and can request a new link', async () => {
    const api = routeApi(
      fetchSpy,
      {
        'GET /api/v1/auth/config': CONFIG,
        'POST /api/v1/auth/email-verification/request': new Response(JSON.stringify(ACCEPTED), { status: 202 }),
        'GET /api/v1/dashboard/summary': {},
      },
      { ...testUser, email_verified: false },
    );
    renderAt('/classify');
    expect(await screen.findByText('Confirm your email address')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Send a new link' }));
    expect(await screen.findByText('Check your inbox')).toBeInTheDocument();
    expect(api.calls.find((c) => c.key.endsWith('/email-verification/request'))?.body).toEqual({ email: testUser.email });
  });

  it('shows no banner for a verified user, and asks the server nothing about it', async () => {
    routeApi(fetchSpy, {});
    renderAt('/classify');
    await screen.findByRole('navigation', { name: 'Main' });
    expect(screen.queryByText('Confirm your email address')).not.toBeInTheDocument();
    expect(dataCalls(fetchSpy).some(([url]) => String(url).endsWith('/auth/config'))).toBe(false);
  });

  it('does not promise a link when the server cannot send e-mail', async () => {
    routeApi(fetchSpy, { 'GET /api/v1/auth/config': { ...CONFIG, email_verification_available: false } }, { ...testUser, email_verified: false });
    renderAt('/classify');
    await screen.findByRole('navigation', { name: 'Main' });
    await waitFor(() => expect(dataCalls(fetchSpy).some(([url]) => String(url).endsWith('/auth/config'))).toBe(true));
    expect(screen.queryByText('Confirm your email address')).not.toBeInTheDocument();
  });

  it('offers to resend the confirmation link when sign-in needs a verified address', async () => {
    const calls = anonymousApi({
      'POST /api/v1/auth/login': errorReply(403, 'email_not_verified', 'verify'),
      'POST /api/v1/auth/email-verification/request': new Response(JSON.stringify(ACCEPTED), { status: 202 }),
    });
    renderAt('/sign-in');
    await userEvent.type(await screen.findByLabelText(/Email address/), 'asha@example.org');
    await userEvent.type(screen.getByLabelText(/^Password/), 'a long passphrase here');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText(/Confirm your email address before signing in/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Send a new confirmation link' }));
    expect(await screen.findByText('Link requested')).toBeInTheDocument();
    expect(calls.find((c) => c.key.endsWith('/email-verification/request'))?.body).toEqual({ email: 'asha@example.org' });
  });
});
