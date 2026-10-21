import type { Mock } from 'vitest';
import { resetSessionForTests, SESSION_HINT_KEY } from '@/services/session';
import type { AuthResponse, SessionUser } from '@/services/session';

export const testUser: SessionUser = {
  id: '11111111-1111-4111-8111-111111111111',
  email: 'asha@example.org',
  full_name: 'Asha Verma',
  roles: ['citizen'],
  permissions: ['waste_reports:create', 'classification:predict', 'sorting_guide:read', 'marketplace:read'],
  email_verified: true,
  mfa_enrollment_required: false,
};

export const authResponse = (user: SessionUser = testUser, token = 'test-access-token'): AuthResponse => ({
  access_token: token,
  token_type: 'bearer',
  expires_in: 900,
  user,
});

export const isRefresh = (url: unknown): boolean => String(url).endsWith('/api/v1/auth/refresh');

/** Start every test from a clean, signed-out client. */
export function resetSession(): void {
  resetSessionForTests();
  window.localStorage.clear();
}

/**
 * Make the app believe a session exists: the hint is set, and `/auth/refresh` (the real restore
 * path) answers with `user`. Everything else goes to `otherwise`, which defaults to 404.
 */
export function signInViaRefresh(
  fetchMock: Mock,
  user: SessionUser = testUser,
  otherwise: (url: string, init?: RequestInit) => Response | Promise<Response> = () =>
    new Response('{}', { status: 404 }),
): void {
  window.localStorage.setItem(SESSION_HINT_KEY, '1');
  fetchMock.mockImplementation((url: string, init?: RequestInit) =>
    Promise.resolve(isRefresh(url) ? Response.json(authResponse(user)) : otherwise(url, init)),
  );
}

/** Fetch calls other than the session restore. */
export const dataCalls = (fetchMock: Mock): unknown[][] =>
  fetchMock.mock.calls.filter(([url]) => !isRefresh(url));
