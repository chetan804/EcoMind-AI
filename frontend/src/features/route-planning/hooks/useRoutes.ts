import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createPlan, fetchPlan, fetchRoadRoute, fetchPlans, planAction, type PlanFilters } from '../api/routes-api';

export const usePlans = (f: PlanFilters) => useQuery({ queryKey: ['routes', 'list', f], queryFn: ({ signal }) => fetchPlans(f, signal) });
export const usePlan = (id: string) => useQuery({ queryKey: ['routes', 'detail', id], queryFn: ({ signal }) => fetchPlan(id, signal) });

export function useCreatePlan() {
  const client = useQueryClient();
  return useMutation({ mutationFn: createPlan, onSuccess: () => client.invalidateQueries({ queryKey: ['routes'] }) });
}

export function usePlanAction(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { action: 'publish' | 'cancel'; reason?: string }) => planAction(id, v.action, v.reason),
    onSuccess: () => Promise.all([client.invalidateQueries({ queryKey: ['routes'] }), client.invalidateQueries({ queryKey: ['notifications'] })]),
  });
}

/** Each road-route request is a billable provider call, so it is made once per dialog open and
 * again only when the user asks for a recompute. */
export const useRoadRoute = (id: string, enabled: boolean) =>
  useQuery({
    queryKey: ['routes', 'road-route', id],
    queryFn: ({ signal }) => fetchRoadRoute(id, signal),
    enabled,
    staleTime: Infinity,
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
