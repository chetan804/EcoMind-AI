/**
 * Client session (who is signed in, their permissions, token handling). Cross-cutting
 * infrastructure like `api-client`: every feature may use it, so it lives here and not in the
 * auth feature (which owns only the sign-in and sign-up screens).
 */
export { useAuth, type Auth } from './useAuth';
export { changePassword, type AuthResponse, type SessionUser } from './auth-api';
export {
  adoptAuthResponse,
  clearSession,
  getAccessToken,
  getSessionState,
  resetSessionForTests,
  SESSION_HINT_KEY,
  type SessionState,
  type SessionStatus,
} from './session-store';
