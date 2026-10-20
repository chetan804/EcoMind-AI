import { useCallback, useEffect, useSyncExternalStore } from 'react';
import {
  bootstrapSession,
  getSessionState,
  signIn,
  signOut,
  signUp,
  subscribeToSession,
  type SessionState,
} from './session-store';

export interface Auth extends SessionState {
  /** True when the signed-in user holds the permission. UX only: the server enforces access. */
  can: (permission: string) => boolean;
  signIn: typeof signIn;
  signUp: typeof signUp;
  signOut: typeof signOut;
}

/** Current session. The first caller triggers the one-time restore from the refresh cookie. */
export function useAuth(): Auth {
  const session = useSyncExternalStore(subscribeToSession, getSessionState, getSessionState);
  useEffect(() => {
    void bootstrapSession();
  }, []);
  const can = useCallback(
    (permission: string) => session.user?.permissions.includes(permission) ?? false,
    [session.user],
  );
  return { ...session, can, signIn, signUp, signOut };
}
