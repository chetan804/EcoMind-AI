import { QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState, type ReactNode } from 'react';
import { getSessionState, subscribeToSession } from '@/services/session/session-store';
import { createQueryClient } from './query-client';

/**
 * Empties the query cache whenever a signed-in session ends (sign-out, expired or revoked
 * refresh token), so the next person using this browser never sees the previous user's data.
 */
function ClearCacheOnSignOut() {
  const queryClient = useQueryClient();
  useEffect(() => {
    let wasAuthenticated = getSessionState().status === 'authenticated';
    return subscribeToSession(() => {
      const isAuthenticated = getSessionState().status === 'authenticated';
      if (wasAuthenticated && !isAuthenticated) queryClient.clear();
      wasAuthenticated = isAuthenticated;
    });
  }, [queryClient]);
  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <ClearCacheOnSignOut />
      {children}
    </QueryClientProvider>
  );
}
