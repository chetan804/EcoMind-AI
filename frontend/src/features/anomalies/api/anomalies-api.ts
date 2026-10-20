import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { decimal, nullableDecimal, pageOf, uuid } from '@/services/schemas';

export const alertSchema = z.object({
  id: uuid,
  metric: z.string(),
  data_kind: z.enum(['platform', 'public_reference']),
  unit: z.string(),
  severity: z.enum(['info', 'warning', 'critical']),
  status: z.enum(['open', 'acknowledged', 'resolved', 'false_positive']),
  window_start: z.string(),
  window_end: z.string(),
  observed_value: decimal,
  expected_value: decimal,
  threshold_value: nullableDecimal,
  detector_name: z.string(),
  detector_version: z.string(),
  explanation: z.string(),
  detected_at: z.string(),
  acknowledged_at: z.string().nullable(),
  resolved_at: z.string().nullable(),
});
export type Alert = z.infer<typeof alertSchema>;

const scanSchema = z.object({
  series: z.string(),
  data_kind: z.string(),
  detector: z.string(),
  weeks_scanned: z.number().int(),
  weeks_considered: z.number().int(),
  flagged: z.number().int(),
  created: z.number().int(),
  already_recorded: z.number().int(),
  alerts: z.array(alertSchema),
  caveat: z.string(),
});
export type ScanResult = z.infer<typeof scanSchema>;

export interface AlertFilters {
  page: number;
  status: string;
  severity: string;
  data_kind: string;
}

export const fetchAlerts = (f: AlertFilters, signal?: AbortSignal) =>
  getJson('/anomalies', pageOf(alertSchema), { ...f, page_size: 20 }, signal);

export type AlertAction = 'acknowledge' | 'resolve' | 'false-positive';
export const transitionAlert = (id: string, action: AlertAction, note: string) =>
  sendJson('POST', `/anomalies/${id}/${action}`, alertSchema, note ? { note } : {});

export const scanSeries = (body: { series: string; lookback_weeks: number }) => sendJson('POST', '/anomalies/scan', scanSchema, body);
