import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  fetchCollectionTracking,
  fetchLatestPositions,
  fetchLocationHistory,
  fetchRouteTracking,
  fetchTrackingConfig,
  postSimulatedLocation,
  resetSimulation,
} from '../api/tracking-api';

export const POLL_MS = 15_000;
export const MAX_POLL_MS = 120_000;

/** Exponential backoff between polls while the server keeps failing; back to POLL_MS on success. */
export function pollingInterval(consecutiveFailures: number): number {
  return Math.min(MAX_POLL_MS, POLL_MS * 2 ** Math.min(consecutiveFailures, 6));
}

const failures = new Map<string, number>();

/** Wrap a fetcher so consecutive failures are counted per key (for the backoff above). */
function counted<T>(key: string, fetcher: (signal?: AbortSignal) => Promise<T>) {
  return async ({ signal }: { signal?: AbortSignal }): Promise<T> => {
    try {
      const result = await fetcher(signal);
      failures.set(key, 0);
      return result;
    } catch (error) {
      failures.set(key, (failures.get(key) ?? 0) + 1);
      throw error;
    }
  };
}

const interval = (key: string) => () => pollingInterval(failures.get(key) ?? 0);

/** Poll only while the tab is visible (TanStack's default refetchIntervalInBackground=false). */
export function useLatestPositions(enabled: boolean, includeSimulated = false) {
  const key = `latest:${includeSimulated}`;
  return useQuery({
    queryKey: ['tracking', 'latest', includeSimulated],
    queryFn: counted(key, (signal) => fetchLatestPositions(includeSimulated, signal)),
    enabled,
    refetchInterval: interval(key),
  });
}

export function useRouteTracking(planId: string | null, includeSimulated: boolean) {
  const key = `route:${planId}:${includeSimulated}`;
  return useQuery({
    queryKey: ['tracking', 'route', planId, includeSimulated],
    queryFn: counted(key, (signal) => fetchRouteTracking(planId as string, includeSimulated, signal)),
    enabled: planId !== null,
    refetchInterval: interval(key),
  });
}

export function useCollectionTracking(taskId: string, enabled: boolean) {
  const key = `collection:${taskId}`;
  return useQuery({
    queryKey: ['tracking', 'collection', taskId],
    queryFn: counted(key, (signal) => fetchCollectionTracking(taskId, signal)),
    enabled,
    refetchInterval: interval(key),
  });
}

export const useTrackingConfig = (enabled: boolean) =>
  useQuery({ queryKey: ['tracking', 'config'], queryFn: ({ signal }) => fetchTrackingConfig(signal), enabled, staleTime: 5 * 60_000 });

export const useLocationHistory = (vehicleId: string | null) =>
  useQuery({
    queryKey: ['tracking', 'history', vehicleId],
    queryFn: ({ signal }) => fetchLocationHistory(vehicleId as string, signal),
    enabled: vehicleId !== null,
  });

export function useSimulation() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: ['tracking'] });
  return {
    post: useMutation({
      mutationFn: (v: { vehicleId: string; body: Record<string, unknown> }) => postSimulatedLocation(v.vehicleId, v.body),
      onSuccess: refresh,
    }),
    reset: useMutation({ mutationFn: (vehicleId: string) => resetSimulation(vehicleId), onSuccess: refresh }),
  };
}
