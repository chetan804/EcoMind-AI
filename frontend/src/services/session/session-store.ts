import { ApiError, configureAuthHooks } from '@/services/api-client';
import * as authApi from './auth-api';
import type { AuthResponse, SessionUser } from './auth-api';

/**
 * Client session state. Framework-free so it can be tested directly; React reads it through
 * `useAuth` (useSyncExternalStore).
 *
 * Security decisions:
 * - The access token lives only in this module's memory. It is never written to localStorage,
 *   sessionStorage or a cookie, so a script that reads storage cannot steal it. A page reload
 *   gets a new one from the HttpOnly refresh cookie.
 * - The refresh token is never visible to JavaScript (HttpOnly cookie).
 * - localStorage holds one non-secret hint ("a session probably exists") purely to avoid a
 *   pointless refresh call, and a 401 in the console, for first-time anonymous visitors.
 * - Concurrent refreshes share one in-flight request. The server rotates the token on every use,
 *   so two parallel refreshes of the same token would otherwise race.
 */

export type SessionStatus = 'unknown' | 'authenticated' | 'anonymous';

export interface SessionState {
  status: SessionStatus;
  user: SessionUser | null;
}

export const SESSION_HINT_KEY = 'ecomind.session-hint';

const UNKNOWN: SessionState = { status: 'unknown', user: null };
const ANONYMOUS: SessionState = { status: 'anonymous', user: null };

let state: SessionState = UNKNOWN;
let accessToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;
let bootstrapInFlight: Promise<void> | null = null;
const listeners = new Set<() => void>();

function setState(next: SessionState): void {
  state = next;
  for (const listener of listeners) listener();
}

function hasHint(): boolean {
  try {
    return window.localStorage.getItem(SESSION_HINT_KEY) === '1';
  } catch {
    return false; // storage blocked: fall back to always trying
  }
}

function writeHint(on: boolean): void {
  try {
    if (on) window.localStorage.setItem(SESSION_HINT_KEY, '1');
    else window.localStorage.removeItem(SESSION_HINT_KEY);
  } catch {
    // Storage is unavailable (private mode, quota). The hint is an optimisation only.
  }
}

export const getSessionState = (): SessionState => state;
export const getAccessToken = (): string | null => accessToken;

export function subscribeToSession(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function adopt(response: AuthResponse): SessionUser {
  accessToken = response.access_token;
  writeHint(true);
  setState({ status: 'authenticated', user: response.user });
  return response.user;
}

/** Drop all local session state (no network). Used on sign-out and when refresh fails. */
export function clearSession(): void {
  accessToken = null;
  writeHint(false);
  setState(ANONYMOUS);
}

/**
 * Exchange the refresh cookie for a new access token. Resolves true when a session is active.
 * A network failure keeps the current state (the server was not reached, so we learned nothing);
 * any definite rejection ends the session.
 */
export function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      adopt(await authApi.refresh());
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status !== 0 && error.status < 500) clearSession();
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

/** Called once at startup: restore a session from the refresh cookie if one probably exists. */
export function bootstrapSession(): Promise<void> {
  if (state.status !== 'unknown') return Promise.resolve();
  bootstrapInFlight ??= (async () => {
    try {
      if (!hasHint()) {
        setState(ANONYMOUS);
        return;
      }
      const restored = await refreshSession();
      // A network/5xx failure leaves the status unknown; treat the user as signed out for now.
      if (!restored && state.status === 'unknown') setState(ANONYMOUS);
    } finally {
      bootstrapInFlight = null;
    }
  })();
  return bootstrapInFlight;
}

export async function signIn(email: string, password: string): Promise<SessionUser> {
  return adopt(await authApi.login(email, password));
}

export async function signUp(input: { email: string; password: string; full_name: string }): Promise<SessionUser> {
  return adopt(await authApi.register(input));
}

/** Always ends the local session, even if the server could not be reached. */
export async function signOut(): Promise<void> {
  try {
    await authApi.logout();
  } catch {
    // The server-side session will expire on its own; the user must still be signed out here.
  } finally {
    clearSession();
  }
}

/** Replace the cached user with the server's current view (after a password change, say). */
export function adoptAuthResponse(response: AuthResponse): void {
  adopt(response);
}

function onStorage(event: StorageEvent): void {
  // Another tab signed out (hint removed): follow it without a network call.
  if (event.key === SESSION_HINT_KEY && event.newValue === null && state.status === 'authenticated') {
    accessToken = null;
    setState(ANONYMOUS);
  }
}

if (typeof window !== 'undefined') window.addEventListener('storage', onStorage);

configureAuthHooks({ getAccessToken, refreshAccessToken: refreshSession });

/** Test helper: return the module to its initial state. */
export function resetSessionForTests(): void {
  accessToken = null;
  refreshInFlight = null;
  bootstrapInFlight = null;
  state = UNKNOWN;
  writeHint(false);
  listeners.clear();
}
