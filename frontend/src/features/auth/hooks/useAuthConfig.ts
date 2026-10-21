import { useQuery } from '@tanstack/react-query';
import { fetchAuthConfig } from '@/services/session';

/** What account recovery the server supports (needs e-mail delivery). Cached: it changes only on deploy. */
export function useAuthConfig() {
  return useQuery({
    queryKey: ['auth', 'config'],
    queryFn: ({ signal }) => fetchAuthConfig(signal),
    staleTime: 5 * 60_000,
  });
}
