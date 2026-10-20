import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { countSchema, nullableDecimal, pageOf, uuid } from '@/services/schemas';

export const INCIDENT_TYPES = ['illegal_dumping', 'overflowing_bin', 'hazardous_waste', 'missed_collection', 'open_burning', 'other'] as const;
export const INCIDENT_STATUSES = ['open', 'acknowledged', 'in_progress', 'resolved', 'dismissed'] as const;

export const incidentSchema = z.object({
  id: uuid,
  reporter_id: uuid,
  assigned_to_id: uuid.nullable(),
  incident_type: z.enum(INCIDENT_TYPES),
  status: z.enum(INCIDENT_STATUSES),
  title: z.string(),
  description: z.string().nullable(),
  address_text: z.string().nullable(),
  latitude: nullableDecimal,
  longitude: nullableDecimal,
  photo_content_path: z.string().nullish(),
  resolved_at: z.string().nullable(),
  resolution_notes: z.string().nullable(),
  created_at: z.string(),
});
export type Incident = z.infer<typeof incidentSchema>;

const summarySchema = z.object({
  total: z.number().int(),
  open_incidents: z.number().int(),
  unassigned_open: z.number().int(),
  by_status: z.array(countSchema),
  by_type: z.array(countSchema),
});

export interface IncidentFilters {
  page: number;
  q: string;
  status: string;
  incident_type: string;
  unassigned: boolean;
}

export const fetchIncidents = (f: IncidentFilters, signal?: AbortSignal) =>
  getJson('/community-incidents', pageOf(incidentSchema), { page_size: 20, sort_by: 'created_at', order: 'desc', ...f }, signal);
export const fetchIncidentSummary = (signal?: AbortSignal) => getJson('/community-incidents/summary', summarySchema, undefined, signal);
export const createIncident = (body: Record<string, unknown>) => sendJson('POST', '/community-incidents', incidentSchema, body);
export const assignIncident = (id: string, assignee_id: string) => sendJson('POST', `/community-incidents/${id}/assign`, incidentSchema, { assignee_id });
export const setIncidentStatus = (id: string, status: string, notes?: string) =>
  sendJson('POST', `/community-incidents/${id}/status`, incidentSchema, { status, notes });
