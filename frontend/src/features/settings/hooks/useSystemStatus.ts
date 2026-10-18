import { useQuery } from '@tanstack/react-query';
import { fetchLiveness, fetchReadiness } from '../api/system-status';

export function useSystemStatus() {
  const liveness = useQuery({ queryKey: ['system-status', 'liveness'], queryFn: ({ signal }) => fetchLiveness(signal) });
  const readiness = useQuery({ queryKey: ['system-status', 'readiness'], queryFn: ({ signal }) => fetchReadiness(signal) });
  return {
    liveness,
    readiness,
    refetch: () => Promise.all([liveness.refetch(), readiness.refetch()]),
  };
}
