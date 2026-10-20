import { ApiError, apiRequest } from '@/services/api-client';
import {
  SESSION_HINT_KEY,
  bootstrapSession,
  completeMfaSignIn,
  getAccessToken,
  getSessionState,
  refreshSession,
  signIn,
  signOut,
} from '@/services/session/session-store';
import { authResponse, resetSession, testUser } from '../helpers/session';

const fetchMock = vi.fn();
const apiError = (code: string, status: number) =>
  Response.json({ error: { code, message: code, details: null, request_id: 'r' } }, { status });
const urlOf = (call: unknown[]) => String(call[0]);

beforeEach(() => {
  resetSession();
  fetchMock.mockReset();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe('session store', () => {
  it('starts unknown, and anonymous without a network call when no session was ever seen', async () => {
    expect(getSessionState().status).toBe('unknown');
    await bootstrapSession();
    expect(getSessionState()).toEqual({ status: 'anonymous', user: null });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('restores a session from the refresh cookie when the hint is present', async () => {
    window.localStorage.setItem(SESSION_HINT_KEY, '1');
    fetchMock.mockResolvedValue(Response.json(authResponse()));
    await bootstrapSession();
    expect(getSessionState().status).toBe('authenticated');
    expect(getSessionState().user?.email).toBe(testUser.email);
    expect(getAccessToken()).toBe('test-access-token');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/auth/refresh');
    expect(init).toMatchObject({ method: 'POST', credentials: 'include', headers: { 'X-CSRF-Protection': '1' } });
  });

  it('never writes the access token anywhere persistent', async () => {
    fetchMock.mockResolvedValue(Response.json(authResponse(testUser, 'super-secret-token')));
    await signIn('a@b.co', 'pw');
    expect(getAccessToken()).toBe('super-secret-token');
    expect(JSON.stringify({ ...window.localStorage, ...window.sessionStorage })).not.toContain('super-secret');
    expect(document.cookie).not.toContain('super-secret');
  });

  it('a password step that needs a second factor creates no session and no hint', async () => {
    fetchMock.mockResolvedValue(Response.json({ mfa_required: true, mfa_token: 'challenge', expires_in: 300 }));
    const result = await signIn('a@b.co', 'pw');
    expect(result).toEqual({ status: 'mfa_required', mfaToken: 'challenge' });
    expect(getSessionState().status).not.toBe('authenticated');
    expect(getAccessToken()).toBeNull();
    expect(window.localStorage.getItem(SESSION_HINT_KEY)).toBeNull();
  });

  it('completing the second factor starts the session', async () => {
    fetchMock.mockResolvedValue(Response.json(authResponse()));
    const user = await completeMfaSignIn('challenge', '123456');
    expect(user.email).toBe(testUser.email);
    expect(getSessionState().status).toBe('authenticated');
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/auth/mfa/verify');
    expect(JSON.parse(String(init.body))).toEqual({ mfa_token: 'challenge', code: '123456' });
  });

  it('shares one in-flight refresh between concurrent callers (the server rotates on every use)', async () => {
    fetchMock.mockResolvedValue(Response.json(authResponse()));
    const results = await Promise.all([refreshSession(), refreshSession(), refreshSession()]);
    expect(results).toEqual([true, true, true]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('ends the session when the server definitively rejects the refresh token', async () => {
    await signInWith();
    fetchMock.mockResolvedValue(apiError('invalid_refresh_token', 401));
    expect(await refreshSession()).toBe(false);
    expect(getSessionState().status).toBe('anonymous');
    expect(getAccessToken()).toBeNull();
    expect(window.localStorage.getItem(SESSION_HINT_KEY)).toBeNull();
  });

  it('keeps the session when the server cannot be reached or is failing (nothing was learned)', async () => {
    await signInWith();
    fetchMock.mockRejectedValue(new TypeError('offline'));
    expect(await refreshSession()).toBe(false);
    expect(getSessionState().status).toBe('authenticated');

    fetchMock.mockResolvedValue(apiError('internal_error', 503));
    expect(await refreshSession()).toBe(false);
    expect(getSessionState().status).toBe('authenticated');
  });

  it('signOut clears local state even when the server call fails', async () => {
    await signInWith();
    fetchMock.mockRejectedValue(new TypeError('offline'));
    await signOut();
    expect(getSessionState().status).toBe('anonymous');
    expect(getAccessToken()).toBeNull();
  });

  it('follows a sign-out performed in another tab', async () => {
    await signInWith();
    window.localStorage.removeItem(SESSION_HINT_KEY);
    window.dispatchEvent(new StorageEvent('storage', { key: SESSION_HINT_KEY, newValue: null }));
    expect(getSessionState().status).toBe('anonymous');
    expect(getAccessToken()).toBeNull();
  });
});

describe('apiRequest with a session', () => {
  it('sends the bearer token on authenticated requests', async () => {
    await signInWith();
    fetchMock.mockResolvedValue(Response.json({ ok: true }));
    await apiRequest('/things');
    const init = fetchMock.mock.calls.at(-1)?.[1] as RequestInit;
    expect(init.headers).toMatchObject({ Authorization: 'Bearer test-access-token' });
  });

  it('does not attach the token to public calls', async () => {
    await signInWith();
    fetchMock.mockResolvedValue(Response.json({ ok: true }));
    await apiRequest('/public', { authenticated: false });
    const init = fetchMock.mock.calls.at(-1)?.[1] as RequestInit;
    expect(JSON.stringify(init.headers)).not.toContain('Authorization');
  });

  it('refreshes once on 401 and retries the request with the new token', async () => {
    await signInWith();
    fetchMock.mockReset();
    fetchMock
      .mockResolvedValueOnce(apiError('unauthenticated', 401))
      .mockResolvedValueOnce(Response.json(authResponse(testUser, 'renewed-token')))
      .mockResolvedValueOnce(Response.json({ id: 7 }));
    const result = await apiRequest<{ id: number }>('/things/7');
    expect(result).toEqual({ id: 7 });
    expect(fetchMock.mock.calls.map(urlOf)).toEqual(['/api/v1/things/7', '/api/v1/auth/refresh', '/api/v1/things/7']);
    const retry = fetchMock.mock.calls[2]?.[1] as RequestInit;
    expect(retry.headers).toMatchObject({ Authorization: 'Bearer renewed-token' });
  });

  it('retries only once: a second 401 is surfaced, with no refresh loop', async () => {
    await signInWith();
    fetchMock.mockReset();
    fetchMock
      .mockResolvedValueOnce(apiError('unauthenticated', 401))
      .mockResolvedValueOnce(Response.json(authResponse()))
      .mockResolvedValueOnce(apiError('unauthenticated', 401));
    const error = await apiRequest('/things').catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it('surfaces the 401 when the refresh fails, and signs the user out', async () => {
    await signInWith();
    fetchMock.mockReset();
    fetchMock
      .mockResolvedValueOnce(apiError('unauthenticated', 401))
      .mockResolvedValueOnce(apiError('invalid_refresh_token', 401));
    await expect(apiRequest('/things')).rejects.toMatchObject({ status: 401 });
    expect(getSessionState().status).toBe('anonymous');
  });

  it('does not try to refresh for 403 or for requests marked public', async () => {
    await signInWith();
    fetchMock.mockReset();
    fetchMock.mockResolvedValue(apiError('forbidden', 403));
    await expect(apiRequest('/admin')).rejects.toMatchObject({ status: 403 });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    fetchMock.mockReset();
    fetchMock.mockResolvedValue(apiError('invalid_credentials', 401));
    await expect(apiRequest('/auth/login', { authenticated: false })).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('exposes Retry-After on 429 responses', async () => {
    fetchMock.mockResolvedValue(
      Response.json({ error: { code: 'rate_limited', message: 'slow down', details: null, request_id: 'r' } }, {
        status: 429,
        headers: { 'Retry-After': '42' },
      }),
    );
    await expect(apiRequest('/x', { authenticated: false })).rejects.toMatchObject({ status: 429, retryAfterSeconds: 42 });
  });
});

async function signInWith() {
  fetchMock.mockResolvedValueOnce(Response.json(authResponse()));
  await signIn('asha@example.org', 'pw');
}
