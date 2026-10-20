import type { ReactNode } from 'react';
import { Forbidden } from '@/components/feedback/Forbidden';
import { useAuth } from '@/services/session';

/**
 * Renders `children` only when the signed-in user holds every permission in `permissions`
 * (and, if `anyOf` is given, at least one of those). UX only: the server enforces access.
 */
export function RequirePermission({
  permissions = [],
  anyOf,
  children,
}: {
  permissions?: string[];
  anyOf?: string[];
  children: ReactNode;
}) {
  const { can } = useAuth();
  const allowed = permissions.every(can) && (anyOf === undefined || anyOf.some(can));
  return allowed ? children : <Forbidden />;
}
