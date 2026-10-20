import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { nullableDecimal, pageOf, uuid } from '@/services/schemas';

export const REPORT_STATUSES = ['submitted', 'under_review', 'verified', 'rejected', 'closed'] as const;

const mediaSchema = z.object({
  id: uuid,
  content_type: z.string(),
  size_bytes: z.number().int(),
  width_px: z.number().int().nullable(),
  height_px: z.number().int().nullable(),
  content_path: z.string(),
});
export type Media = z.infer<typeof mediaSchema>;

export const reportSchema = z.object({
  id: uuid,
  reporter_id: uuid,
  status: z.enum(REPORT_STATUSES),
  title: z.string(),
  description: z.string().nullable(),
  address_text: z.string().nullable(),
  latitude: nullableDecimal,
  longitude: nullableDecimal,
  estimated_weight_kg: nullableDecimal,
  reported_at: z.string(),
  media: z.array(mediaSchema),
});
export type Report = z.infer<typeof reportSchema>;

export interface ReportFilters {
  page: number;
  q: string;
  status: string;
  mine: boolean;
}

export const fetchReports = (f: ReportFilters, signal?: AbortSignal) =>
  getJson('/waste-reports', pageOf(reportSchema), { page_size: 20, sort_by: 'reported_at', order: 'desc', ...f }, signal);
export const fetchReport = (id: string, signal?: AbortSignal) => getJson(`/waste-reports/${id}`, reportSchema, undefined, signal);
export const createReport = (body: Record<string, unknown>) => sendJson('POST', '/waste-reports', reportSchema, body);
export const reviewReport = (id: string, body: { status: string; reason?: string }) =>
  sendJson('POST', `/waste-reports/${id}/review`, reportSchema, body);
