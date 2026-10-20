import { useQuery } from '@tanstack/react-query';
import { fetchOverview, fetchWeeklyTrend } from '../api/analytics-api';

export const useOverview = (windowDays: number) =>
  useQuery({ queryKey: ['analytics', 'overview', windowDays], queryFn: ({ signal }) => fetchOverview(windowDays, signal) });

export const useWeeklyTrend = (weeks: number) =>
  useQuery({ queryKey: ['analytics', 'weekly-trend', weeks], queryFn: ({ signal }) => fetchWeeklyTrend(weeks, signal) });
