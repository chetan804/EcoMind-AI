import { z } from 'zod';
import { getJson, sendJson } from '@/services/list-api';
import { decimal, pageOf, uuid } from '@/services/schemas';

export const PASSPORT_STATUSES = ['active', 'in_processing', 'recovered', 'retired'] as const;
export const EVENT_TYPES = ['created', 'collected', 'transferred', 'received', 'processed', 'verified'] as const;

export const passportSchema = z.object({
  id: uuid,
  passport_code: z.string(),
  material_category_id: uuid,
  status: z.enum(PASSPORT_STATUSES),
  description: z.string().nullable(),
  weight_kg: decimal,
  origin_collection_task_id: uuid.nullable(),
  recovery_record_id: uuid.nullable(),
  current_facility_id: uuid.nullable(),
  created_at: z.string(),
});
export type Passport = z.infer<typeof passportSchema>;

export const passportDetailSchema = passportSchema.extend({
  events: z.array(
    z.object({
      id: uuid,
      sequence: z.number().int(),
      event_type: z.enum(EVENT_TYPES),
      occurred_at: z.string(),
      from_facility_id: uuid.nullable(),
      to_facility_id: uuid.nullable(),
      notes: z.string().nullable(),
    }),
  ),
});
export type PassportDetail = z.infer<typeof passportDetailSchema>;

export const integritySchema = z.object({ passport_code: z.string(), valid: z.boolean(), events: z.number().int(), problems: z.array(z.string()), basis: z.string().optional() });

export interface PassportFilters {
  page: number;
  q: string;
  status: string;
}

export const fetchPassports = (f: PassportFilters, signal?: AbortSignal) =>
  getJson('/material-passports', pageOf(passportSchema), { page_size: 20, sort_by: 'created_at', order: 'desc', ...f }, signal);
export const fetchPassport = (id: string, signal?: AbortSignal) => getJson(`/material-passports/${id}`, passportDetailSchema, undefined, signal);
export const fetchIntegrity = (id: string, signal?: AbortSignal) => getJson(`/material-passports/${id}/integrity`, integritySchema, undefined, signal);
export const createPassport = (body: Record<string, unknown>) => sendJson('POST', '/material-passports', passportSchema, body);
export const addEvent = (id: string, body: Record<string, unknown>) => sendJson('POST', `/material-passports/${id}/events`, z.unknown(), body);
export const linkRecovery = (id: string, recovery_record_id: string) => sendJson('POST', `/material-passports/${id}/recovery`, passportSchema, { recovery_record_id });
