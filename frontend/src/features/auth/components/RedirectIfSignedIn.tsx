import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router';
import { useAuth } from '@/services/session';
import { safeRedirectTarget } from '../utils/auth-errors';

/** Keeps signed-in users off the sign-in / sign-up screens, returning them where they came from. */
export function RedirectIfSignedIn({ children, fallback = '/dashboard' }: { children: ReactNode; fallback?: string }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === 'authenticated') {
    const from = (location.state as { from?: unknown } | null)?.from;
    return <Navigate to={safeRedirectTarget(from, fallback)} replace />;
  }
  return children;
}
