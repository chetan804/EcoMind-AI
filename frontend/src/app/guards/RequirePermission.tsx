import type { ReactNode } from 'react';
import { Forbidden } from '@/components/feedback/Forbidden';
import { useAuth } from '@/services/session';

/** Renders `children` only when the signed-in user holds every listed permission. */
export function RequirePermission({ permissions, children }: { permissions: string[]; children: ReactNode }) {
  const { can } = useAuth();
  return permissions.every(can) ? children : <Forbidden />;
}
