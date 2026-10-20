import { apiRequest } from '@/services/api-client';

export interface SessionUser {
  id: string;
  email: string;
  full_name: string;
  roles: string[];
  permissions: string[];
}

export interface AuthResponse {
  access_token: string;
  token_type: 'bearer';
  /** Access token lifetime in seconds. */
  expires_in: number;
  user: SessionUser;
}

/** Sign-in step one for an account with two-factor authentication: no session exists yet. */
export interface MfaChallenge {
  mfa_required: true;
  mfa_token: string;
  /** Seconds the challenge stays valid. */
  expires_in: number;
}

export const isMfaChallenge = (value: AuthResponse | MfaChallenge): value is MfaChallenge =>
  'mfa_required' in value && value.mfa_required === true;

/** The cookie-authenticated endpoints reject requests without this header (CSRF defence). */
const CSRF_HEADERS = { 'X-CSRF-Protection': '1' } as const;

// Sign-in, sign-up and refresh never carry a bearer token and must not trigger a refresh retry.
export const login = (email: string, password: string) =>
  apiRequest<AuthResponse | MfaChallenge>('/auth/login', { method: 'POST', body: { email, password }, authenticated: false });

export const verifyMfa = (mfaToken: string, code: string) =>
  apiRequest<AuthResponse>('/auth/mfa/verify', { method: 'POST', body: { mfa_token: mfaToken, code }, authenticated: false });

export const register = (input: { email: string; password: string; full_name: string }) =>
  apiRequest<AuthResponse>('/auth/register', { method: 'POST', body: input, authenticated: false });

export const refresh = () =>
  apiRequest<AuthResponse>('/auth/refresh', { method: 'POST', headers: CSRF_HEADERS, authenticated: false });

export const logout = () =>
  apiRequest<null>('/auth/logout', { method: 'POST', headers: CSRF_HEADERS, authenticated: false });

export const fetchMe = () => apiRequest<SessionUser>('/auth/me');

export const changePassword = (input: { current_password: string; new_password: string }) =>
  apiRequest<AuthResponse>('/auth/change-password', { method: 'POST', body: input });
