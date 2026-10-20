import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { decimal } from '@/services/schemas';

export const seriesInfoSchema = z.object({
  ref: z.string(),
  name: z.string(),
  data_kind: z.enum(['platform', 'public_reference']),
  label: z.string(),
  unit: z.string(),
  granularity: z.string(),
  points: z.number().int(),
  first_period: z.string().nullable(),
  last_period: z.string().nullable(),
  interpolated_points: z.number().int(),
  provenance: z
    .object({ source_url: z.string(), source_commit: z.string(), licence_note: z.string(), processing_note: z.string() })
    .nullish(),
});
export type SeriesInfo = z.infer<typeof seriesInfoSchema>;

const historySchema = z.object({
  series: seriesInfoSchema,
  points: z.array(z.object({ period_start: z.string(), value: decimal, interpolated: z.boolean() })),
});
export type SeriesHistory = z.infer<typeof historySchema>;

const forecastPoint = z.object({
  period_start: z.string(),
  period_end: z.string(),
  predicted: decimal,
  lower: decimal,
  upper: decimal,
});
export type ForecastPoint = z.infer<typeof forecastPoint>;

const nullableNumber = z.number().nullable();
export const forecastSchema = z.object({
  series: seriesInfoSchema,
  model: z.object({
    name: z.string(),
    engine_version: z.string(),
    parameters: z.record(z.string(), z.number()),
    selection: z.string(),
  }),
  backtest: z.object({
    horizon_weeks: z.number().int(),
    origins: z.number().int(),
    candidate_mae: z.record(z.string(), z.number()),
    selected_mae: nullableNumber,
    naive_mae: nullableNumber,
    mae_vs_naive: nullableNumber,
    beats_naive: z.boolean().nullable(),
  }),
  interval_level: z.number(),
  points: z.array(forecastPoint),
  caveats: z.array(z.string()),
  generated_at: z.string(),
  saved: z.boolean(),
});
export type Forecast = z.infer<typeof forecastSchema>;

const storedSchema = z.object({
  series: seriesInfoSchema,
  generated_at: z.string().nullable(),
  model_name: z.string().nullable(),
  model_version: z.string().nullable(),
  points: z.array(forecastPoint),
});
export type StoredForecast = z.infer<typeof storedSchema>;

export const fetchSeriesList = (signal?: AbortSignal) => getJson('/forecasting/series', z.array(seriesInfoSchema), undefined, signal);
export const fetchHistory = (series: string, signal?: AbortSignal) => getJson('/forecasting/series/history', historySchema, { series }, signal);
export const fetchLatestForecast = (series: string, signal?: AbortSignal) =>
  getJson('/forecasting/forecasts/latest', storedSchema, { series }, signal);
export const runForecast = (body: { series: string; horizon_weeks: number; save: boolean }) =>
  sendJson('POST', '/forecasting/forecasts', forecastSchema, body);
