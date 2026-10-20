import { getJson } from '@/services/list-api';
import { overviewSchema, weeklyTrendSchema } from './schemas';

export const fetchOverview = (windowDays: number, signal?: AbortSignal) =>
  getJson('/analytics/overview', overviewSchema, { window_days: windowDays }, signal);

export const fetchWeeklyTrend = (weeks: number, signal?: AbortSignal) =>
  getJson('/analytics/weekly-trend', weeklyTrendSchema, { weeks }, signal);
