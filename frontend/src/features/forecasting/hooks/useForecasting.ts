import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchHistory, fetchLatestForecast, fetchSeriesList, runForecast } from '../api/forecasting-api';

export const useSeriesList = (enabled = true) =>
  useQuery({ queryKey: ['forecasting', 'series'], queryFn: ({ signal }) => fetchSeriesList(signal), enabled });

export const useHistory = (series: string) =>
  useQuery({
    queryKey: ['forecasting', 'history', series],
    queryFn: ({ signal }) => fetchHistory(series, signal),
    enabled: series !== '',
  });

export const useLatestForecast = (series: string) =>
  useQuery({
    queryKey: ['forecasting', 'latest', series],
    queryFn: ({ signal }) => fetchLatestForecast(series, signal),
    enabled: series !== '',
  });

export function useRunForecast() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: runForecast,
    onSuccess: (_data, variables) => client.invalidateQueries({ queryKey: ['forecasting', 'latest', variables.series] }),
  });
}
