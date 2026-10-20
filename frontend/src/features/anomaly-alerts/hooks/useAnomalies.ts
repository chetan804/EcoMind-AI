import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchAlerts, scanSeries, transitionAlert, type AlertAction, type AlertFilters } from '../api/anomalies-api';

const key = ['anomalies'] as const;

export const useAlerts = (filters: AlertFilters) =>
  useQuery({ queryKey: [...key, 'list', filters], queryFn: ({ signal }) => fetchAlerts(filters, signal) });

export function useTransition() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (v: { id: string; action: AlertAction; note: string }) => transitionAlert(v.id, v.action, v.note),
    onSuccess: () => client.invalidateQueries({ queryKey: key }),
  });
}

export function useScan() {
  const client = useQueryClient();
  return useMutation({ mutationFn: scanSeries, onSuccess: () => client.invalidateQueries({ queryKey: key }) });
}
