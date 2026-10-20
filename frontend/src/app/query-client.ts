import { QueryClient } from '@tanstack/react-query';
import { isRetryableError } from '@/services/error-handler';

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: false,
        retry: (failureCount, error) => isRetryableError(error) && failureCount < 2,
      },
    },
  });
}
